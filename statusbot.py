#!/usr/bin/env python

import imp
import json
import socket
import re
import random
import irc.bot
import pyrcon
import ts3py
import commands

class Command:
    def __init__(self, name, function, password = False):
        self.name = name
        self.function = function
        self.password = password

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

        self.loadCommands()

    def loadCommands(self):
        imp.reload(commands)
        self.commands = []
        for attr in dir(commands):
            if "cmd_" in attr:
                offset = 4
                pw = False
                if "pw_" in attr:
                    offset += 3
                    pw = True

                self.commands.append(Command(attr[offset:], getattr(commands, attr), pw))
                    
        self.commands.append(Command("reload", self.cmd_reload, True))

    def cmd_reload(self, bot, issuedBy, data):
        """reloads commands"""
        self.loadCommands()
        self.pm(issuedBy, "Commands reloaded")

    """
    #------------------------------------------#
    #            IRC-Related Stuff             #
    #------------------------------------------#
    """
    
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

    """
    #------------------------------------------#
    #            Command Execution             #
    #------------------------------------------#
    """

    def executeCommand(self, ev, priv):
        issuedBy = ev.source.nick
        text = ev.arguments[0][1:].split(" ")
        command = text[0].lower()
        data = " ".join(text[1:])

        if priv:
            self.target = issuedBy
        else:
            self.target = self.channel

        for c in self.commands:
            if command == c.name:
                if c.password and (data[:5] == self.password or issuedBy in self.loggedin) or\
                    not c.password:
                    c.function(self, issuedBy, data)
                    return
                else:
                    self.reply("WRONG PASSWORD, NOB!")
                    return

        self.reply("Command not found: " + command)

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
