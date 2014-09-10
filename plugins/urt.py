import socket
import time
import re
import pyrcon
import subprocess
import threading

class UrTPlugin():
    def __init__(self, bot):
        self.bot = bot
        self.livechat_on = False

    def startup(self, config):
        self.bot.registerCommand("servers", self.cmd_servers)
        self.bot.registerCommand("players", self.cmd_players)
        self.bot.registerCommand("maps", self.cmd_maps)
        self.bot.registerCommand("info", self.cmd_info)
        self.bot.registerCommand("status", self.cmd_status)
        self.bot.registerCommand("ss", self.cmd_setserver)
        self.bot.registerCommand("rcon", self.cmd_rcon, True)
        self.bot.registerCommand(".", self.cmd_rconsay, True)
        self.bot.registerCommand("livechat", self.cmd_livechat, True)
        self.bot.registerCommand("lc", self.cmd_livechat, True)
        self.bot.registerCommand("stoplivechat", self.cmd_stoplivechat, True)
        self.bot.registerCommand("stoplc", self.cmd_stoplivechat, True)

        self.bot.registerCommand("p", self.cmd_players)
        self.bot.registerCommand("s", self.cmd_status)
        self.bot.registerCommand("i", self.cmd_info)
        self.bot.registerCommand("m", self.cmd_maps)

        self.servers = {}
        for line in open("servers.txt", "r").readlines():
            parts = line.strip().split(" ")
            addr = parts[-1]
            name = " ".join(parts[:-1])
            self.servers[name] = addr

        self.ts3servers = {}
        for line in open("ts3.txt", "r").readlines():
            parts = line.strip().split(" ")
            addr = parts[-1]
            name = " ".join(parts[:-1])
            self.ts3servers[name] = addr

    def shutdown(self):
        self.livechat_on = False

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

        r = sock.recv(3096)
        return r[4:].decode()

    def serverHelper(self, string):
        if string == ".." and self.lastServer is not None:
            return self.lastServer

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
            self.bot.reply("No servers found matching \x02{}\x02.".format(string))
        elif len(matches) > 1:
            self.bot.reply("There are multiple matches for \x02{}\x02: {}".format(string, ", ".join(matches)))
        else:
            self.lastServer = (matches[0], self.servers[matches[0]])
            return matches[0], self.servers[matches[0]] 

        return None, None
 
    def parseChat(self, data, playersCmd = False, statusCmd = False):
        name, server = self.serverHelper(data)

        if server is None:
            return

        longLen = len(max(self.servers, key=len))

        try:
            r = self.sockSend(server, "getstatus")
        except socket.timeout:
            if playersCmd:
                self.bot.reply("\x02{}\x02 server is down".format(name))
            else:
                self.bot.reply("(N/A)    \x02{}\x02 \x034SERVER IS DOWN".format(\
                    (name + ":").ljust(longLen + 2)))

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

        server_info = r.split("\n")
        raw_vars = server_info[1].split("\\")[1:]
        server_vars = {raw_vars[i]:raw_vars[i+1] for i in range(0, len(raw_vars), 2)}

        players = [p for p in server_info[2:] if p]
        clean_players = [re.sub("\^[0-9-]", "", player) for player in players]
        clanmembers = len([x for x in players if self.bot.clan in x])

        if playersCmd:
            if not clean_players:
                self.bot.reply("There are no players on \x02{}\x02".format(name))
            else:
                self.bot.reply("\x02Players on {} ({}/{})\x02: {}".format(name, len(players), server_vars["sv_maxclients"], 
                    ", ".join(p.split(" ")[2][1:-1] for p in clean_players)))
        elif statusCmd:
            gamemode = _GAMEMODES[int(server_vars["g_gametype"])]
            if clanmembers:
                self.bot.reply("{}\x02{}\x02 {}{} {}".format(\
                ("(" + gamemode + ")").ljust(7),
                (name + ":").ljust(longLen + 2),
                (str(len(players)) + "/" + server_vars["sv_maxclients"]).ljust(8), 
                ("(" + str(clanmembers) + " " + self.bot.clan + ")").ljust(12),
                server_vars["mapname"]))
            else:
                self.bot.reply("{}\x02{}\x02 {} {}".format(\
                    ("(" + gamemode + ")").ljust(7),
                    (name + ":").ljust(longLen + 2),
                    (str(len(players)) + "/" + server_vars["sv_maxclients"]).ljust(20), 
                    server_vars["mapname"]))

    def cmd_servers(self, issuedBy, data):
        """displays server list"""
        self.bot.reply("\x02Servers\x02: {}".format(", ".join(self.servers)))
        self.bot.reply("\x02TS3 Servers\x02: {}".format(", ".join(self.ts3servers)))

    def cmd_players(self, issuedBy, data):
        """[server] - show current players on a server"""
        if data:
            self.parseChat(data, True, False)
        else:
            for s in self.servers:
                time.sleep(1)
                self.parseChat(s, True, False)
        
    def cmd_status(self, issuedBy, data):
        """[server] - show server information"""
        if data:
            self.parseChat(data, False, True)
        else:
            for s in self.servers:
                time.sleep(1)
                self.parseChat(s, False, True)

    def cmd_info(self, issuedBy, data):
        """[server] - show server connection info"""
        if not data:
            return

        name, server = self.serverHelper(data)

        if server is None:
            return

        self.bot.reply("\x02{}\x02 connection info: /connect {}".format(name, server))

    def cmd_maps(self, issuedBy, data):
        """[server] - list maps on a server"""
        if not data:
            return

        name, server = self.serverHelper(data)
        parts = server.split(":")
        host = parts[0]
        port = int(parts[1])
        conn = pyrcon.RConnection(host, port, self.bot.rconpassword)

        m = conn.send("dir .")
        m = m.split("\n")
        m = [m for m in m if ".pk3" in m and "zUrT42" not in m]
        m = [m.replace(".pk3", "").replace("ut42_", "").replace("ut4_", "").replace("_", " ") for m in m]
        n = [tuple(m[i:i+5]) for i in range(0, len(m), 5)]

        self.bot.reply("\x02{}\x02 maps on \x02{}\x02: {}".format(len(m), name, ", ".join(n[0])))
        for i in range(1, len(n)):
            time.sleep(1)
            self.bot.reply("{}".format(", ".join(n[i])))

    def cmd_setserver(self, issuedBy, data):
        """[server] - set the last server to send commands to"""
        if not data:
            return

        name, server = self.serverHelper(data)

        if server is None:
            return

        server = self.lastServer

    def get_chat(self, f):
        p = subprocess.Popen(["ssh", "example@example.com", "tail", "-f", "-n 0", "/path/to/logs/" + f + ".log"], stdout=subprocess.PIPE)
        while self.livechat_on:
            chat = p.stdout.readline()
            chat = chat.decode()
            chat = chat.split("\n")
            chat = [c for c in chat if "say:" in c]
            for i in range(0, len(chat)):
                chats = chat[i]
                chats = chats.split()
                self.bot.reply(" ".join(chats[3:]))

    def cmd_livechat(self, issuedBy, data):
        """[server] - show live chat output from a server"""
        name, server = self.serverHelper(data)

        if name.lower() == "hottie's":
            threading.Thread(target=self.get_chat, args=("ctf",)).start()
        elif name.lower() == "gravy's":
            threading.Thread(target=self.get_chat, args=("ts",)).start()
        elif name.lower() == "billy's":
            threading.Thread(target=self.get_chat, args=("sr8",)).start()
        elif name.lower() == "bongs'n'dongs":
            threading.Thread(target=self.get_chat, args=("uzts",)).start()

        self.livechat_on = True

    def cmd_stoplivechat(self, issuedBy, data):
        """- stop livechat output"""
        self.livechat_on = False

    def cmd_rconsay(self, issuedBy, data):
        """[chat] - quicker way to chat to recent server"""
        if not data:
            return

        if self.lastServer is None:
            self.bot.reply("No recent servers used")
            return

        name, server = self.lastServer
        parts = server.split(":")
        host = parts[0]
        port = int(parts[1])
        rcon = pyrcon.RConnection(host, port, self.bot.rconpassword)

        rcon.send("say ^7>[^2irc^7]{}^3: {}".format(issuedBy, data[0:]))

    def cmd_rcon(self, issuedBy, data):
        """[server] [command] [args...] - send an rcon command to a server"""
        data = data.split(" ")
        name = self.serverHelper(data[0])
        server = self.serverHelper(data[0])

        if server is None:
            return

        parts = server[1].split(":")
        host = parts[0]
        port = int(parts[1])
        rcon = pyrcon.RConnection(host, port, self.bot.rconpassword)

        if data[1] == "say":
            rcon.send("say \"^7>[^2irc^7]{}^3: {}\"".format(issuedBy, " ".join(data[2:])))
            return

        info = rcon.send("{}".format(" ".join(data[1:]))).split("\n")
        info = [i for i in info if i]

        if "Bad rconpassword." in info:
            self.bot.reply("Bad rconpassword")
        elif len(info) == 2:
            clean_info = [re.sub("\^[0-9-]", "", _info) for _info in info]
            self.bot.reply("".join(clean_info[1]))
        elif data[1] == "dumpuser":
            for i in range(3, len(info)):
                self.bot.pm(issuedBy, "{}".format(info[i]))
        else:
            self.bot.reply("\x02{}\x02 command sent to \x02{}\x02".format(" ".join(data[1:]), name[0]))