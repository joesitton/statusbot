#!/usr/bin/env python

import irc.bot
import json
import socket
import pyrcon
import re
import random
#import ts3py

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
            parts = line.split(" ")
            addr = parts[-1]
            name = " ".join(parts[:-1])
            self.servers[name] = addr

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
        self.parseChat(ev)

    def on_pubmsg(self, conn, ev):
        self.parseChat(ev)
        if self.password in ev.arguments[0]:
            self.new_password()

    def parseChat(self, ev):
        if (ev.arguments[0][0] in self.cmdPrefixes):
            self.executeCommand(ev)

    def _on_nick(self, conn, ev):
        old = ev.source.nick
        new = ev.target

        if old in self.loggedin:
            self.loggedin.remove(old)
            self.loggedin.append(new)

    def new_password(self):
        self.password = genRandomString(5)
        self._msg_owners(self.password)

    def executeCommand(self, ev):
        issuedBy = ev.source.nick
        text = ev.arguments[0][1:].split(" ")
        command = text[0].lower()
        data = " ".join(text[1:])

        found = False

        try:
            commandFunc = getattr(self, "cmd_" + command)
            commandFunc(issuedBy, data)
            found = True
        except AttributeError:
            if data[:5] == self.password or issuedBy in self.loggedin:
                try:
                    commandFunc = getattr(self, "pw_cmd_" + command)
                    commandFunc(issuedBy, data)
                    found = True
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
            sock.settimeout(10)
            sock.connect((host, port))
            sock.send(b"\xFF\xFF\xFF\xFF" + data.encode())
        except socket.Timeouterror:
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

        try:
            r = self.sockSend(server, "getstatus")
        except socket.Timeouterror:
            return

        sparts = r.split("\n")

        players = [p for p in sparts[2:] if p]
        nplayers = [re.sub("\^[0-9-]", "", player) for player in players]
        clanmems = " ".join(players).count(self.clan)

        rawvars = sparts[1].split("\\")[1:]
        svars = {rawvars[i]:rawvars[i+1] for i in range(0, len(rawvars), 2)}

        if playersCmd:
            if not players:
                self.reply("There are no players on \x02" + name + "\x02")
            else:
                self.reply("\x02Players on {} ({}/{}):\x02  ".format(name, len(players), svars["sv_maxclients"]) + 
                           ", ".join(p.split(" ")[2][1:-1] for p in nplayers))
        elif serverCmd:
            self.sendcmd = self.rcon.send("{}".format(" ".join(data[1:])))
            infos = self.sendcmd.split("\n")
            infos = [i for i in infos if i]
            if "Bad rconpassword." in infos:
                self.reply("Bad rconpassword")
            elif len(infos) == 2:
                ninfo = [re.sub("\^[0-9-]", "", info) for info in infos]
                self.reply("".join(ninfo[1]))
            else:
                self.sendcmd
                self.reply("\x02{}\x02 command sent to \x02{}\x02".format(" ".join(data[1:]), name))
        else:
            gamemode = self._GAMEMODES[int(svars["g_gametype"])]
            if clanmems:
                self.reply("\x02{}\x02 ({}):    {}/{} ({} {})    {}".format(name, gamemode, len(players), svars["sv_maxclients"], clanmems, self.clan, svars["mapname"]))
            else:
                self.reply("\x02{}\x02 ({}):    {}/{}    {}".format(name, gamemode, len(players), svars["sv_maxclients"], svars["mapname"]))

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

    def pw_cmd_login(self, issuedBy, data):
        """.login - logs you in"""
        if issuedBy not in self.loggedin:
            self.loggedin.append(issuedBy)
            self.reply("{} has logged in".format(issuedBy))
        else:
            self.pm(issuedBy, "You are already logged in")

    def pw_cmd_die(self, issuedBy, data):
        """.die - kills the bot"""
        if issuedBy in self.loggedin:
            if data:
                self.die("{}".format(data))
            else:
                self.die("Leaving")
        else:
            self.pm(issuedBy, "You don't have access to that command")

    def pw_cmd_rcon(self, issuedBy, data):
        """.rcon [server] [command] [args...] - send an rcon command to a server"""
        if issuedBy in self.loggedin:
            if data:
                self.parseStatus(data, False, True)
            else:
                for s in self.servers:
                    self.parseStatus(s, False, True)
        else:
            self.pm(issuedBy, "You don't have access to that command")

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
