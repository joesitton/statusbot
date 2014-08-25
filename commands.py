import re
import socket
import pyrcon
import ts3py
import time

"""
#------------------------------------------#
#             Sock Connection              #
#------------------------------------------#
"""

def sockSend(bot, address, data):
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

"""
#------------------------------------------#
#            Command Helpers               #
#------------------------------------------#
"""

def serverHelper(bot, string):
    string = string.lower()
    matches = []

    if not string:
        return

    for s in bot.servers:
        if string == s.lower():
            matches = [s]
            break

        if string in s.lower():
            matches.append(s)
    
    if not matches:
        bot.reply("No servers found matching '{}' .".format(string))
    elif len(matches) > 1:
        bot.reply("There are multiple matches for  {}: {}".format(string, ", ".join(matches)))
    else:
        return matches[0], bot.servers[matches[0]]

    return None, None

def ts3Helper(bot, string):
    string = string.lower()
    matches = []

    if not string:
        return

    for s in bot.ts3servers:
        if string == s.lower():
            matches = [s]
            break

        if string in s.lower():
            matches.append(s)

    if not matches:
        bot.reply("No servers found matching '{}'.".format(string))
    elif len(matches) > 1:
        bot.reply("There are multiple matches for {}: {}".format(string, ", ".join(matches)))
    else:
        return matches[0], bot.ts3servers[matches[0]]

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

"""
#------------------------------------------#
#               Chat Parser                #
#------------------------------------------#
"""

def parseStatus(bot, data, playersCmd = False, serverCmd = False):
    data = data.split(" ")
    name, server = serverHelper(bot, data[0])

    if server is None:
        return

    longLen = len(max(bot.servers, key = len))
    
    try:
        r = sockSend(bot, server, "getstatus")
    except socket.timeout:
        if playersCmd:
            bot.reply("{} server i".format(name))
        elif not serverCmd:
            bot.reply("(N/A)  \x02{}\x02 \x034SERVER IS DOWN".format(\
                (name + ":").ljust(longLen + 2)))
        return

    sparts = r.split("\n")

    players = [p for p in sparts[2:] if p]
    nplayers = [re.sub("\^[0-9-]", "", player) for player in players]
    clanmems = len([x for x in players if bot.clan in x])

    rawvars = sparts[1].split("\\")[1:]
    svars = {rawvars[i]:rawvars[i+1] for i in range(0, len(rawvars), 2)}

    if playersCmd:
        if not players:
            bot.reply("There are no players on \x02" + name + "\x02")
        else:
            bot.reply("\x02Players on {} ({}/{}):\x02  ".format(name, len(players), svars["sv_maxclients"]) + 
                       ", ".join(p.split(" ")[2][1:-1] for p in nplayers))
    elif serverCmd:
        parts = server.split(":")
        host = parts[0]
        port = int(parts[1])
        rcon = pyrcon.RConnection(host, port, bot.rconpasswd)    
        sendcmd = rcon.send("{}".format(" ".join(data[1:])))
        infos = sendcmd.split("\n")
        infos = [i for i in infos if i]
        if "Bad rconpassword." in infos:
            bot.reply("Bad rconpassword")
        elif len(infos) == 2:
            ninfo = [re.sub("\^[0-9-]", "", info) for info in infos]
            bot.reply("".join(ninfo[1]))
        elif data[1] == "dumpuser":
            for i in range(3, len(infos)):
                bot.pm(issuedBy, "{}".format(infos[i]))
        else:
            sendcmd
            bot.reply("\x02{}\x02 command sent to \x02{}\x02".format(" ".join(data[1:]), name))
    else:
        gamemode = _GAMEMODES[int(svars["g_gametype"])]
        if clanmems:
            bot.reply("{}\x02{}\x02 {}{} {}".format(\
                ("(" + gamemode + ")").ljust(7),
                (name + ":").ljust(longLen + 2),
                (str(len(players)) + "/" + svars["sv_maxclients"]).ljust(8), 
                ("(" + str(clanmems) + " " + bot.clan + ")").ljust(12),
                svars["mapname"]))
        else:
            bot.reply("{}\x02{}\x02 {} {}".format(\
                ("(" + gamemode + ")").ljust(7),
                (name + ":").ljust(longLen + 2),
                (str(len(players)) + "/" + svars["sv_maxclients"]).ljust(20), 
                svars["mapname"]))

"""
#------------------------------------------#
#               Commands                   #
#------------------------------------------#
"""

def cmd_help(bot, issuedBy, data):
    """[command] - displays this message"""
    if data == "":
        for c in bot.commands:
            bot.reply(".{} {}".format(c.name, c.function.__doc__))
    else:
        for c in bot.commands:
            if data == c.name:
                bot.reply(".{} {}".format(c.name, c.function.__doc__))
                return
        bot.reply("Command not found: " + data)

def cmd_servers(bot, issuedBy, data):
    """display server list"""
    bot.reply("\x02Servers:\x02 " + ", ".join(bot.servers))
    bot.reply("\x02TS3 Servers:\x02 " + ", ".join(bot.ts3servers))

def cmd_players(bot, issuedBy, data):
    """[server] - show current players on the server"""
    if data:
        parseStatus(bot, data, True, False)
    else:
        for s in bot.servers:
            parseStatus(bot, s, True, False)

def cmd_status(bot, issuedBy, data):
    """[server] - show server information"""
    if data:
        parseStatus(bot, data, False, False)
    else:
        for s in bot.servers:
            parseStatus(bot, s, False, False)

def cmd_ts3(bot, issuedBy, data):
    """[server] - show people connected to a ts3 server"""
    data = data.split(" ")
    address = ts3Helper(bot, data[0])
    name = ts3Helper(bot, data[0])

    parts = address[1].split(":")
    host = parts[0]
    port = 10011
    vs_id = parts[1]

    connection = ts3py.TS3Query(host, port)
    connection.connect(host, port)
    connection.use(vs_id)

    people = connection.clients()
    people = [p for p in people if not "Unknown" in p]

    bot.reply("\x02{}\x02 clients on \x02{}\x02 TS3: {}".format(len(people), name[0], ", ".join(people)))

def cmd_info(bot, issuedBy, data):
    """[server] - show connection info for a server"""
    if not data:
        return

    data = data.split(" ")
    info = serverHelper(bot, data[0])

    if None in info:
        return

    try:
        bot.reply("\x02{}\x02 connection info: /connect {}".format(info[0], info[1]))
    except:
        return

def cmd_maps(bot, issuedBy, data):
    """[server] - list the maps on a server"""
    if not data:
        return

    server = serverHelper(bot, data)
    parts = server[1].split(":")

    host = parts[0]
    port = int(parts[1])

    conn = pyrcon.RConnection(host, port, bot.rconpasswd)
    m = conn.send("dir .")
    m = m.split("\n")
    m = [m for m in m if ".pk3" in m and "zUrT42" not in m]
    m = [m.replace(".pk3", "").replace("ut42_", "").replace("ut4_", "").replace("_", " ") for m in m]
    n = [tuple(m[i:i+5]) for i in range(0, len(m), 5)]

    bot.reply("\x02{}\x02 maps on \x02{}:\x02 {}".format(len(m), server[0], ", ".join(n[0])))
    for i in range(1, len(n)):
        time.sleep(1)
        bot.reply("{}".format(", ".join(n[i])))

def cmd_quotes(bot, issuedBy, data):
    """[player] - show quotes from clan members"""
    quotes = [
        "<nikkerz> almost took in another foster named grandma dog | <ducci> too bad she's named after a Fallin Angels member",
        "Holla... I'll mail you my mouth and you can use it to suck your dick (c) Clear",
        "I'll enchant your butthole with my penis (c) FragTag",
        "I just took a shit bigger than falco's ego (c) ReigN*",
        "That's why I don't want a dog, it would start barking at things and I would think it's barking at a ghost and I would be scared (c) Jason",
        "I remember feeling so manly when I used to shoot my BB gun (c) Jason",
        "you were inside me for a second there, that was a weird feeling. (c) Clear",
        "I've been sitting here drinking my pee and its not that bad, its just water (c) Creeper",
        "were you drunk last night or just weeded? (c) 0sch",
        "carrots used to be blue my fucking ass (c) Zod",
        "so how did team canada going (c) FragTag",
        "Dude, i would have so many beers with you right now, id fuck an animal (c) 0sch",
        "Now in farm simulator, are you a farmer, a tractor, or an actual farm? (c) Clear",
        "its just me and tampee (c) Tampee",
        "i asked him if he was gay, and thats when he went soft on me (c) Russa",
        "that boner seems like a good fit around here (c) Tampee",
        "he will try to sneak a sausage in (c) Russa",
        "hey falco, you want to be on a team with falco? (c) FragTag"
    ]

    matches = [q for q in quotes if data.lower() in q.lower()]
    for i in range(0, len(matches)):
        time.sleep(1)
        bot.reply("{}".format(matches[i]))

"""
#------------------------------------------#
#               Aliases                    #
#------------------------------------------#
"""

def cmd_s(bot, issuedBy, data):
    """alias for .status"""
    cmd_status(bot, issuedBy, data)

def cmd_p(bot, issuedBy, data):
    """alias for .players"""
    cmd_players(bot, issuedBy, data)

"""
#------------------------------------------#
#             Admin Commands               #
#------------------------------------------#
"""

def pw_cmd_login(bot, issuedBy, data):
    """logs you in"""
    if issuedBy not in bot.loggedin:
        bot.loggedin.append(issuedBy)
        bot.reply("{} has logged in".format(issuedBy))
    else:
        bot.pm(issuedBy, "You are already logged in")

def pw_cmd_die(bot, issuedBy, data):
    """kills the bot"""
    if issuedBy in bot.loggedin:
        if data:
            bot.die("{}".format(data))
        else:
            bot.die("Leaving")
    else:
        bot.pm(issuedBy, "You don't have access to that command")

def pw_cmd_rcon(bot, issuedBy, data):
    """[server] [command] [args...] - send an rcon command to a server"""
    if issuedBy in bot.loggedin:
        if data:
            parseStatus(bot, data, False, True)
        else:
            for s in bot.servers:
                parseStatus(bot, s, False, True)
    else:
        bot.pm(issuedBy, "You don't have access to that command")