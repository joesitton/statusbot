#!/usr/bin/env python

import irc.bot
import json
import socket

class Pugbot(irc.bot.SingleServerIRCBot):
    def __init__(self, config):
        super(Pugbot, self).__init__([(config["server"], config["port"])], config["nick"], config["nick"])
        self.channel = config["channel"]
        self.target = self.channel
        self.cmdPrefixes = config["prefixes"]
        self.owners = config["owners"]

        self.servers = {}
        for line in open("servers.txt", "r").readlines():
            parts = line.split(" ")
            self.servers[parts[0]] = parts[1]

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

    def sockConnection(self, data):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        address = self.servers[data]
        parts = address.split(":")
        host = parts[0]
        port = parts[1]

        self.sock.connect((host, int(port)))
        self.sock.send(b"\xFF\xFF\xFF\xFFgetstatus") #todo: move all this junk out of this func
        self.response = self.sock.recv(1024)
        self.response = self.response[4:].decode("UTF-8")

        self.sparts = self.response.split("\n")


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
        self.reply("Servers: " + ", ".join(self.servers))

    def cmd_kill(self, issuedBy, data):
        """.kill - kills the bot"""
        if issuedBy in self.owners:
            self.die("Leaving")
        else:
            self.reply("You don't have access to that command")

    def cmd_players(self, issuedBy, data):
        """.players [server] - show current players on the server"""
        self.sockConnection(data)

        players = []

        try:
            for i in range(2, 64):
                players.append(self.sparts[i])
        except IndexError:
            if len(players) == 1:
                self.reply("There are no players on {0}'s".format(data))
            else:
                print(players)
                self.reply("Players: " + ", ".join(players))

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
