#!/usr/bin/env python

import irc.bot
import json
import socket
import pyrcon
import re
import random
import ts3py

def genRandomString(length):
    alpha = "abcdefghijklmnopqrstuvwxyz"
    return "".join(random.choice(alpha) for _ in range(length))

class Pugbot(irc.bot.SingleServerIRCBot):
    def __init__(self, config):
        super(Pugbot, self).__init__([(config["server"], config["port"])], config["nick"], config["nick"])
        self.channel = config["channel"]
        self.target = self.channel
        self.cmdPrefixes = config["prefixes"]
        self.owners = config["owners"]
        self.rconowners = config["rconowners"]
        self.rconpasswd = config["rconpasswd"]
        self.clan = config["clantag"]
        self.loggedin = self.rconowners

        self.servers = {}
        for line in open("servers.txt", "r").readlines():
            parts = line.strip().split(" ")
            addr = parts[-1]
            name = " ".join(parts[:-1])
            self.servers[name] = addr

        self.ts3servers = {}
        for line in open("ts3.txt", "r").readlines():
            parts = line.split(" ")
            addr = parts[-1]
            name = " ".join(parts[:-1])
            self.ts3servers[name] = addr

        # Adds a Latin-1 fallback when UTF-8 decoding doesn't work
        irc.client.ServerConnection.buffer_class = irc.buffer.LenientDecodingLineBuffer
    
    def on_nicknameinuse(self, conn, ev):
        conn.nick(conn.get_nickname() + "_")
    
    def on_ping(self, conn, ev):
        self.connection.pong(ev.target)

    def say(self, msg):
        self.connection.privmsg(self.channel, msg)

    def pm(self, nick, msg):
        self.connection.privmsg(nick, msg)
    
    def reply(self, msg):
        self.connection.privmsg(self.target, msg)

    def on_welcome(self, conn, e):
        conn.join(self.channel)

        self.password = genRandomString(5)
        self._msg_owners(self.password)
        print(self.password)

    def _msg_owners(self, message):
        for owner in self.owners:
            self.pm(owner, message)

    def on_privmsg(self, conn, ev):
        self.parseChat(ev, True)

    def on_pubmsg(self, conn, ev):
        self.parseChat(ev)
        if self.password in ev.arguments[0]:
            self.new_password()

    def parseChat(self, ev, priv = False):
        if (ev.arguments[0][0] in self.cmdPrefixes):
            self.executeCommand(ev, priv)

    def _on_nick(self, conn, ev):
        old = ev.source.nick
        new = ev.target

        if old in self.loggedin:
            self.loggedin.remove(old)
            self.loggedin.append(new)

    def new_password(self):
        self.password = genRandomString(5)
        self._msg_owners(self.password)

    def executeCommand(self, ev, priv):
        self.issuedBy = ev.source.nick
        text = ev.arguments[0][1:].split(" ")
        command = text[0].lower()
        data = " ".join(text[1:])

        if priv:
            self.target = self.issuedBy
        else:
            self.target = self.channel

        found = False

        try:
            commandFunc = getattr(self, "cmd_" + command)
            commandFunc(self.issuedBy, data)
            found = True
        except AttributeError:
            try:
                commandFunc = getattr(self, "a_cmd_" + command)
                found = True
                commandFunc(self.issuedBy, data)
            except AttributeError:
                if data[:5] == self.password or self.issuedBy in self.loggedin:
                    try:
                        commandFunc = getattr(self, "pw_cmd_" + command)
                        found = True
                        commandFunc(self.issuedBy, data)
                    except AttributeError:
                        pass
        
        if not found:
            self.reply("Command not found: " + command)

    def sockSend(self, address, data):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        parts = address.split(":")
        host = parts[0]
        port = int(parts[1])

        try:
            sock.settimeout(3)
            sock.connect((host, port))
            sock.send(b"\xFF\xFF\xFF\xFF" + data.encode())
        except socket.timeout:
            sock.close()
            return

        self.rcon = pyrcon.RConnection(host, port, self.rconpasswd)

        r = sock.recv(3096)
        return r[4:].decode()

    def serverHelper(self, string):
        string = string.lower()
        matches = []

        if not string:
            return

        for s in self.servers:
            if string == s.lower():
                matches = [s]
                break

            if string in s.lower():
                matches.append(s)
        
        if not matches:
            self.reply("No servers found matching  '{}' .".format(string))
        elif len(matches) > 1:
            self.reply("There are multiple matches for  {}: {}".format(string, ", ".join(matches)))
        else:
            return matches[0], self.servers[matches[0]]

        return None, None

    _GAMEMODES = [
        "FFA",
        "LMS",
        "",
        "TDM",
        "TS",
        "FTL",
        "C&H",
        "CTF",
        "BOMB",
        "JUMP"
    ]

    def parseStatus(self, data, playersCmd = False, serverCmd = False):
        data = data.split(" ")
        name, server = self.serverHelper(data[0])

        if server is None:
            return

        longLen = len(max(self.servers, key = len))
        
        try:
            r = self.sockSend(server, "getstatus")
        except socket.timeout:
            if playersCmd:
                self.reply("{} server i".format(name))
            elif not serverCmd:
                self.reply("(N/A)  \x02{}\x02 \x034SERVER IS DOWN".format(\
                    (name + ":").ljust(longLen + 2)))
            return

        sparts = r.split("\n")

        players = [p for p in sparts[2:] if p]
        nplayers = [re.sub("\^[0-9-]", "", player) for player in players]
        clanmems = len([x for x in players if self.clan in x])

        rawvars = sparts[1].split("\\")[1:]
        svars = {rawvars[i]:rawvars[i+1] for i in range(0, len(rawvars), 2)}

        if playersCmd:
            if not players:
                self.reply("There are no players on \x02" + name + "\x02")
            else:
                self.reply("\x02Players on {} ({}/{}):\x02  ".format(name, len(players), svars["sv_maxclients"]) + 
                           ", ".join(p.split(" ")[2][1:-1] for p in nplayers))
        elif serverCmd:
            sendcmd = self.rcon.send("{}".format(" ".join(data[1:])))
            infos = sendcmd.split("\n")
            infos = [i for i in infos if i]
            if "Bad rconpassword." in infos:
                self.reply("Bad rconpassword")
            elif len(infos) == 2:
                ninfo = [re.sub("\^[0-9-]", "", info) for info in infos]
                self.reply("".join(ninfo[1]))
            elif data[1] == "dumpuser":
                for i in range(3, len(infos)):
                    self.pm(self.issuedBy, "{}".format(infos[i]))
            else:
                sendcmd
                self.reply("\x02{}\x02 command sent to \x02{}\x02".format(" ".join(data[1:]), name))
        else:
            gamemode = self._GAMEMODES[int(svars["g_gametype"])]
            if clanmems:
                self.reply("{}\x02{}\x02 {}{} {}".format(\
                    ("(" + gamemode + ")").ljust(7),
                    (name + ":").ljust(longLen + 2),
                    (str(len(players)) + "/" + svars["sv_maxclients"]).ljust(8), 
                    ("(" + str(clanmems) + " " + self.clan + ")").ljust(12),
                    svars["mapname"]))
            else:
                self.reply("{}\x02{}\x02 {} {}".format(\
                    ("(" + gamemode + ")").ljust(7),
                    (name + ":").ljust(longLen + 2),
                    (str(len(players)) + "/" + svars["sv_maxclients"]).ljust(20), 
                    svars["mapname"]))

    def cmd_help(self, issuedBy, data):
        """.help [command] - displays this message"""
        if data == "":
            attrs = sorted(dir(self))
            self.reply("Commands:")
            for attr in attrs:
                if attr[:4] == "cmd_":
                    self.reply(getattr(self, attr).__doc__)
        else:
            try:
                command = getattr(self, "cmd_" + data.lower())
                self.reply(command.__doc__)
            except AttributeError:
                self.reply("Command not found: " + data)

    def cmd_servers(self, issuedBy, data):
        """.servers - display server list"""
        self.reply("\x02Servers:\x02 " + ", ".join(self.servers))
        self.reply("\x02TS3 Servers:\x02 " + ", ".join(self.ts3servers))

    def cmd_players(self, issuedBy, data):
        """.players [server] - show current players on the server"""
        if data:
            self.parseStatus(data, True, False)
        else:
            for s in self.servers:
                self.parseStatus(s, True, False)

    def cmd_status(self, issuedBy, data):
        """.status [server] - show server information"""
        if data:
            self.parseStatus(data, False, False)
        else:
            for s in self.servers:
                self.parseStatus(s, False, False)

    def cmd_ts3(self, issuedBy, data):
        """.ts3 [server] - show people connected to a ts3 server"""
        try:
            address = self.ts3servers[data]
        except KeyError:
            self.reply("Invalid TS3 server: '{}'".format(data))
            return

        parts = address.split(":")
        host = parts[0]
        port = 10011
        vs_id = parts[1]

        connection = ts3py.TS3Query(host, port)
        connection.connect(host, port)
        connection.use(vs_id)

        people = connection.clients()
        people = [p for p in people if not "Unknown" in p]

        self.reply("\x02{}\x02 clients on \x02{}\x02 TS3: {}".format(len(people), data, ", ".join(people)))

    def a_cmd_s(self, issuedBy, data):
        self.cmd_status(issuedBy, data)

    def a_cmd_p(self, issuedBy, data):
        self.cmd_players(issuedBy, data)

    def pw_cmd_login(self, issuedBy, data):
        """.login - logs you in"""
        if self.issuedBy not in self.loggedin:
            self.loggedin.append(self.issuedBy)
            self.reply("{} has logged in".format(self.issuedBy))
        else:
            self.pm(self.issuedBy, "You are already logged in")

    def pw_cmd_die(self, issuedBy, data):
        """.die - kills the bot"""
        if self.issuedBy in self.loggedin:
            if data:
                self.die("{}".format(data))
            else:
                self.die("Leaving")
        else:
            self.pm(self.issuedBy, "You don't have access to that command")

    def pw_cmd_rcon(self, issuedBy, data):
        """.rcon [server] [command] [args...] - send an rcon command to a server"""
        if self.issuedBy in self.loggedin:
            if data:
                self.parseStatus(data, False, True)
            else:
                for s in self.servers:
                    self.parseStatus(s, False, True)
        else:
            self.pm(self.issuedBy, "You don't have access to that command")

def main():
    try:
        configFile = open("config.json", "r")
        config = json.loads(configFile.read())
    except:
        print("Invalid or missing config file. Check if config.json exists and follows the correct format")
        return

    bot = Pugbot(config)
    bot.start()

if __name__ == "__main__":
    main()
