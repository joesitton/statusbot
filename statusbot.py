#!/usr/bin/env python

import irc.bot
import json
import socket
import pyrcon

class Pugbot(irc.bot.SingleServerIRCBot):
    def __init__(self, config):
        super(Pugbot, self).__init__([(config["server"], config["port"])], config["nick"], config["nick"])
        self.channel = config["channel"]
        self.target = self.channel
        self.cmdPrefixes = config["prefixes"]
        self.owners = config["owners"]
        self.password = config["rconpasswd"]

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

    def on_privmsg(self, conn, e):
        self.executeCommand(conn, e, True)

    def on_pubmsg(self, conn, e):
        if (e.arguments[0][0] in self.cmdPrefixes):
            self.executeCommand(conn, e)

    def executeCommand(self, conn, e, private = False):
        issuedBy = e.source.nick
        text = e.arguments[0][1:].split(" ")
        command = text[0].lower()
        data = " ".join(text[1:])

        if private:
            self.target = issuedBy
        else:
            self.target = self.channel

        try:
            commandFunc = getattr(self, "cmd_" + command)
            commandFunc(issuedBy, data)
        except AttributeError:
            self.reply("Command not found: " + command)

    def sockSend(self, address, data):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        parts = address.split(":")
        host = parts[0]
        port = int(parts[1])

        sock.connect((host, port))
        self.rcon = pyrcon.RConnection(host, port, self.password)
        sock.send(b"\xFF\xFF\xFF\xFF" + data.encode())

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
            self.reply("No servers found matching  \x0316,2{}\x03 .".format(string))
        elif len(matches) > 1:
            self.reply("There are multiple matches for  \x0316,2{}:\x03 {}".format(string, ", ".join(matches)))
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

        r = self.sockSend(server, "getstatus")
        sparts = r.split("\n")

        players = [p for p in sparts[2:] if p]

        rawvars = sparts[1].split("\\")[1:]
        svars = {rawvars[i]:rawvars[i+1] for i in range(0, len(rawvars), 2)}

        if playersCmd:
            if not players:
                self.reply("There are no players on \x0316,2" + name + "\x03")
            else:
                self.reply("Players on \x0316,2{}\x03 ({}/{}):  ".format(name, len(players), svars["sv_maxclients"]) + 
                           ", ".join(p.split(" ")[2][1:-1] for p in players))
        elif serverCmd:
            self.rcon.send("{}".format(" ".join(data[1:])))
            self.reply("\x0316,2{}\x03 command sent to \x0316,2{}\x03".format(" ".join(data[1:]), name))
        else:
            gamemode = self._GAMEMODES[int(svars["g_gametype"])]
            self.reply("\x0316,2{}:    {}/{}    {}    {}\x03".format(name, len(players), svars["sv_maxclients"], gamemode, svars["mapname"]))

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
        self.reply("\x0316,2Servers:\x03 " + ", ".join(self.servers))

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

    def cmd_kill(self, issuedBy, data):
        """.kill - kills the bot"""
        if issuedBy in self.owners:
            if data:
                self.die("{}".format(data))
            else:
                self.die("Leaving")
        else:
            self.pm(issuedBy, "You don't have access to that command")

    def cmd_rcon(self, issuedBy, data):
        """.rcon [server] [command] [args...] - send an rcon command to a server"""
        if issuedBy in self.owners:
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
