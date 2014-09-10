import ts3py

class TS3Plugin:
    def __init__(self, bot):
        self.bot = bot

    def startup(self, config):
        self.bot.registerCommand("ts3", self.cmd_ts3)

        self.ts3servers = {}
        for line in open("ts3.txt", "r").readlines():
            parts = line.strip().split(" ")
            addr = parts[-1]
            name = " ".join(parts[:-1])
            self.ts3servers[name] = addr
            
    def shutdown(self):
        pass

    def ts3Helper(self, string):
        string = string.lower()
        matches = []

        if not string:
            return

        for s in self.ts3servers:
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
            return matches[0], self.ts3servers[matches[0]] 

        return None, None

    def cmd_ts3(self, issuedBy, data):
        """[server] - show clients on a ts3 server"""
        if not data:
            return
            
        name, server = self.ts3Helper(data)

        parts = server.split(":")
        host = parts[0]
        port = 10011
        vs_id = parts[1]

        conn = ts3py.TS3Query(host, port)
        conn.connect(host, port)
        conn.use(vs_id)

        people = conn.clients()
        people = [p for p in people if not "Unknown" in p]

        self.bot.reply("\x02{}\x02 clients on \x02{}\x02 TS3: {}".format(len(people), name, ", ".join(people)))