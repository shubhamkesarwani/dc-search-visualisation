from connection import Connection, ConnectionError
import os, random, re, socket, sys, time, string, csv


class search_client():


	def __init__(self): # Initializes to default values all configuration variables and other objects required for the functioning of this system.
		self._download = {} # Container for download manager thread and status variables
		self._config = {} # This dictionary will store all the configuration variables that will subsequently be used by this client.
		self._dir = {} # Application Directory Locations
		self._step = {} # Application Directory Locations
		self.active = False
		self._config["hubcount"] = "0/1/0"

		# debug files
		self._debug_fh = open("debug-log.txt","w+")

		with open('search.csv', 'a+') as output_csvfile:
			fieldnames = ['date', 'ip', 'search_query']
			csv_writer = csv.DictWriter(output_csvfile, fieldnames=fieldnames, delimiter=',')
			csv_writer.writeheader()
		
		# User Details
		self._config["nick"] = "Anonymous" # User Nickname
		self._config["pass"] = "" # User Password
		self._config["status"] = 1 # User Status
		self._config["desc"] = "" # User Description
		self._config["email"] = "" # User EMail Address
		self._config["sharesize"] = 0 # Total size of data shared by the user in bytes
		self._config["operator"] = False # Whether or not this user is an operator on the hub
		# Client Details
		self._config["client"] = "pyDC" # Client Name
		self._config["version"] = "1" # Client Version
		self._config["connection"] = "100" # Connection Speed Indicator (Mbps)
		self._config["mode"] = True # Whether or not this client can act as a server for peer-to-peer transfers.
		self._config["cid"] = "%10d" % (random.randint(0,10**10-1)) # Client ID : CID needs to be pseudorandomly generated with negligible collision probability
		self._config["localhost"] = socket.gethostbyname(socket.gethostname()) # The IP Address of this system
		self._config["group_base"] = "general" # The name of the default group to which an unclassfied nick belongs to.
		self._config["filelist"] = "files.xml.bz2" # The identifier of filelists in _queue
		self._config["savedata"] = "configuration.dat" # The same of the file in which data will be saved
		self._config["sr_count"] = 10 # Maximum number of search results to return per request
		# Hub Details
		self._config["host"] = "10.109.49.49" # The address of the hub to which we want to connect
		self._config["port"] = 411 # The port at which the intended hub is running
		self._config["hubname"] = "" # The name of the hub to which you connect
		self._config["topic"] = "" # The topic of the hub to which you connect
		# Connection Details
		self._config["searchtime_manual"] = 15 # The time in seconds for which a user-initiated search is waiting for more results
		self._config["searchtime_auto"] = 5 # The time in seconds for which an automatic search for TTH alternates is waiting for results
		self._config["retry"] = 3 # Number of times a connection request will be sent to a remote host if it isnt responding
		self._config["wait"] = 5 # Number of seconds to wait between sending repeated connection requests.
		# Negotionation Details
		self._config["lock"] = "Majestic12" # A random string used during authentication
		self._config["key"] = self.lock2key(self._config["lock"]) # Generated using the above lock used during authorization
		self._config["signature"] = "SourceCode" # A random string used during negotiation, conventionally used to indicate client name
		self._config["support"] = "XmlBZList ADCGet TTHF" # The set of protocols that this client supports (space separated). More options: MiniSlots, TTHL, ZLIG
		# Transfer Control
		self._download["upslots"] = 0 # The number of upload slots currently in use
		self._download["maxupslots"] = 3 # The maximum number of upload slots possible
		self._download["downslots"] = 0 # The number of download slots currently in use
		self._download["maxdownslots"] = 5 # The maximum number of download slots possible
		# Step Control
		self._config["step_time"] = 1 # How long the step functions waits before each run
		self._step["active"] = False # Whether or not the step function is running
		self._step["thread"] = None # The thread pointing to the step function
		self._step["function"] = None # The function to be called at every step run
		self._step["args"] = None # Arguments that are provided to and returned by every call of the ste function.
		# Download Manager
		self._config["segment_size"] = 1024*1024*10 # 100MB : Size of blocks to be downloaded from different users
		self._config["download_time"] = 1 # How long the step functions waits before each run
		self._download["active"] = False # Whether the download manager is running
		self._download["thread"] = None # The thread pointing to the download manager function
		# self._download["lock"] = threading.Semaphore() # A lock used to ensure that only one download is being inititated at a time.
		self._config["overwrite"] = False # Whether or not to overwrite existing files with the same name after download.
		# Default Streams/Connections
		self._mainchat = self._debug_fh.write #open("debug-mainchat.txt","w").write #sys.stdout # The function to which mainchat messages are sent
		self._pm = None # The function to which mainchat messages are sent
		self._debug = None # The function to which debug information is to be printed to. Do not use unless actually necessary.
		self._socket = None # A connection to the Hub
		# Persistant Data Structires, except _config
		self._queue = [] # A list containing pseudo-objects of the format: {id,part,parts,type,nick,offset,length,priority,name,size,location,active}
		self._userips = {} # Used to keep track of the IP addresses of users, even if they arent available. Given the more persistant nature of this dictionary, it is rather useful in determining the nickname, given the IP.
		self._groups = { self._config["group_base"]:[] } # A dict of lists, key = groupname, list values = members
		self._filelist = { self._config["group_base"]:[] } # A dict containing group->list_of_dirs_to_be_shared entries. Entries here need to be shared yet.
		# Temporary Data Structures
		self._nicklist = {} # A list of all nicknames connected to this hub
		self._search = {} # A dict containing pointers to search pseudo-objects of the format: socket (a connection type object that sets up a UDP server on which to recieve search results), result (the stream to which results are sent upon arrival), mode (manual or auto)
		self._transfer = [] # A list containing pointers to transfer pseudo-objects of the format: {host,port,mode(active/passive),connection}
		# self._shared = { self._config["group_base"]: xml.dom.minidom.Document() } # A xml.dom object containing the files and folders currently shared.
		
	def connect(self): # Connects to the hub.
		self.debug("Attempting to connect to Hub ...")
		
		# if not self._config["ready"]: return self
		self._socket = Connection({ "name":"DC Hub", "host":self._config["host"], "port":self._config["port"], "type":"tcp", "role":"client", "handler":self.server_handler, "args":{"buffer":""}, "debug":self._debug })
		self.debug("Connected to Hub.")
		return self

	def server_handler(self,data,info,args): # Interacts with the DC, responding to any commands that are sent by it.
		if data is None:
			if "buffer" not in args: args = {"buffer":""}
			return args
		args["buffer"]+=data
		for iteration in range(args["buffer"].count("|")):
			# Isolate a particular command
			length = args["buffer"].index("|")
			if length==0:
				args["buffer"] = args["buffer"][1:]
				continue
			data = args["buffer"][0:length]
			args["buffer"] = args["buffer"][length+1:]
			if data[0]=="<" and self._mainchat: self._mainchat(data+"\n")
			elif data[0]=="$":
				x = data.split()
				if x[0]=="$Lock": self._socket.send("$Supports UserCommand UserIP2 TTHSearch GetZBlock |$Key "+self.lock2key(x[1])+"|$ValidateNick "+self._config["nick"]+"|")
				# elif x[0]=="$Supports": self._config["hub_supports"] = x[1:]
				# elif x[0]=="$HubName":
					# self._config["hubname"] = x[-1]
					# self._mainchat("Hub Name : "+self._config["hubname"]+"\n")
				# elif x[0]=="$GetPass": self._socket.send("$MyPass "+self._config["pass"]+"|")
				# elif x[0]=="$BadPass":
					# self.disconnect()
				elif x[0]=="$Hello":
					if x[1]==self._config["nick"]:
						query_str_hello = "$Version "+self._config["version"]+"|$MyINFO $ALL "+self._config["nick"]+" "+self._config["desc"]+" <"+self._config["client"]+" V:"+str(self._config["version"])+",M:"+("A" if self._config["mode"] else "P")+",H:"+self._config["hubcount"]+",S:"+str(self._download["maxupslots"])+">$ $"+self._config["connection"]+chr(self._config["status"])+"$"+self._config["email"]+"$"+str(self._config["sharesize"])+"$|$GetNickList|"
						print "\n" + query_str_hello + "\n"
						self._socket.send(query_str_hello)
					else:
						try: self._nicklist[x[1]]
						except: self._nicklist[x[1]] = {"operator":False,"bot":False} # $OpList and $BotList commands will soon follow (if required), so we can make this assumption here.
				#elif x[0]=="$LogedIn": self._config["operator"] = True
				# elif x[0]=="$HubTopic":
					# self._config["topic"] = data[10:]
					# self._mainchat("Hub Topic : "+self._config["topic"]+"\n")
				# elif x[0]=="$NickList":
				# 	self._nicklock.acquire()
				# 	for nick in data[10:].split("$$"):
				# 		if nick=="": continue
				# 		try: self._nicklist[nick]
				# 		except KeyError: self._nicklist[nick] = {"operator":False,"bot":False}
				# 		try: self._nicklist[nick]["ip"] = self._userips[nick]
				# 		except KeyError: pass
				# 	self._socket.send("$UserIP "+data[9:]+"|")
				# 	self._nicklock.release()
				elif x[0]=="$UserIP":
					for item in data[8:].split("$$"):
						if item=="": continue
						nick,ip = item.split()
						self._userips[nick] = ip
				# elif x[0]=="$OpList":
				# 	ops = data[8:].split("$$")
				# 	for nick in self._nicklist:
				# 		if nick=="": continue
				# 		self._nicklist[nick]["operator"] = (True if nick in ops else False)
				# elif x[0]=="$BotList":
				# 	bots = data[9:].split("$$")
				# 	for nick in self._nicklist:
				# 		if nick=="": continue
				# 		self._nicklist[nick]["bot"] = (True if nick in bots else False)
				elif x[0]=="$MyINFO":
					nick,desc,conn,flag,email,share = re.findall("^\$MyINFO \$ALL ([^ ]*) ([^\$]*)\$.\$([^\$]*)([^\$])\$([^\$]*)\$([^\$]*)\$",data)[0]
					try: self._config["nicklist"][nick]
					except KeyError: self._nicklist[nick] = {"operator":False,"bot":False}
					self._nicklist[nick]["desc"] = desc
					self._nicklist[nick]["conn"] = conn
					self._nicklist[nick]["flag"] = flag
					self._nicklist[nick]["email"] = email
					self._nicklist[nick]["share"] = share
				# elif x[0]=="$To:":
				# 	info2 = re.findall("^\$To\: ([^ ]*) From: ([^ ]*) \$(.*)$",data)
				# 	if len(info2)==0: continue
				# 	else: info2 = info2[0]
				# 	if self._config["nick"]!=info2[0]: continue
				# 	try: self._pm( info2[1] , time.strftime("%d-%b-%Y %H:%S",time.localtime())+" "+info2[2] )
				# 	except TypeError: pass
				elif x[0]=="$Quit":
					try: del self._nicklist[x[1]]
					except KeyError: pass
				# elif x[0]=="$ForceMove":
				# 	if x[1].count(":")==0: addr = (x[1],411)
				# 	elif x[1].count(":")==1: addr = tuple(x.split(":"))
				# 	else:
				# 		self.debug("Invalid Redirection Address")
				# 		continue
				# 	if self._config["host"]==addr[0] and self._config["port"]==addr[1]:
				# 		self.debug("Redirected to the same hub : "+x[1])
				# 		continue
				# 	self._config["host"],self._config["port"] = addr
				# 	self.reconnect()
				elif x[0]=="$Search": self.search_result_generate(data)
				# elif x[0]=="$SR": self.search_result_process(data)
				# elif x[0]=="$ConnectToMe":
				# 	continue # SHERIFFBOT
				# 	remote = x[2] # This client's mode does not matter here
				# 	d = {"host":remote.split(":")[0], "port":remote.split(":")[1] }
				# 	d["socket"] = Connection({ "name":remote,"host":remote.split(":")[0],"port":remote.split(":")[1],"role":"client","type":"tcp","handler":self.transfer_handler,"args":{"role":"client","transfer":d},"debug":self._debug })
				# 	self._transfer.append(d)
				# elif x[0]=="$RevConnectToMe":
				# 	continue # SHERIFFBOT
				# 	self.connect_remote(x[1],False)
				else: self.debug("Unrecognized Command : "+data)
			else: self.debug("Additional Data : "+data)
			# end of iteration
		return args

	def lock2key(self,lock): # Generates response to $Lock challenge from Direct Connect Servers
		# Written by Benjamin Bruheim; http://wiki.gusari.org/index.php?title=LockToKey%28%29
		lock = [ord(c) for c in lock]
		key = [0]
		for n in range(1,len(lock)):
			key.append(lock[n]^lock[n-1])
		key[0] = lock[0] ^ lock[-1] ^ lock[-2] ^ 5
		for n in range(len(lock)):
			key[n] = ((key[n] << 4) | (key[n] >> 4)) & 255
		result = ""
		for c in key:
			if c in [0, 5, 36, 96, 124, 126]:
				result += "/%%DCN%.3i%%/" % c
			else:
				result += chr(c)
		return result

	def unescape(self,data): # Used to reobtain characters from the HTML entity form.
		match = re.findall("\&\#([0-9]{1,3})\;",data.replace("&amp;","&#38;"));
		for item in match: data = data.replace("&#"+item+";",chr(int(item)));
		return data

	def search_result_generate(self, data):
		# print "\nSEARCH: \n" + data + "\n"
		info = None # Represents that the search pattern is as of now, unrecognized
		if info is None: # Active Mode Search
			info = re.findall("^\$Search ([0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})\:([0-9]{1,5}) ([TF])\?([TF])\?([0-9]*)\?([0-9])\?(.*)$",data)
			if len(info)==0: info = None # No matches, so list will be empty
			else: mode = True # Active
		if info is None: # Passive Mode Search
			info = re.findall("^\$Search (Hub):([^ ]*) ([TF])\?([TF])\?([0-9]*)\?([0-9])\?(.*)$",data)
			if len(info)==0: info = None
			else: mode = False # Passive
		if info is None: # Unrecognized command
			self.debug("Unrecognized search request - ignored : "+data)
			
		
		# Prepare the information available for easy access
		info = list(info[0]); # As there will always be only one match, so only one list item
		info[5] = int(info[5]); # Size Limit
		if info[5]==9: info[6]=info[6][4:] # Remove the initial "TTH/" tag.
		else: 
			info[6] = self.unescape(info[6].replace("$"," ")) # Convert $ back to spaces
			ip_addr = info[0]
			search_query = info[6]
			date_str = time.strftime("%d-%b-%Y %H:%M:%S",time.localtime())
			print "\nIP:"+ip_addr+" QUERY: "+search_query

			# Data storage in csv
			with open('search.csv', 'a+') as output_csvfile:
				fieldnames = ['date', 'ip', 'search_query']
				csv_writer = csv.DictWriter(output_csvfile, fieldnames=fieldnames, delimiter=',')
				# csv_writer.writeheader()
				csv_writer.writerow({'date': date_str,'ip': ip_addr, 'search_query': search_query})


	def configure(self,data): # Allows the users to configure the client according to his wishes.
		# Load data provided by user
		# if self.active(): self.debug("Cannot configure client while the connection is active.")
		# if os.path.isfile(self._dir["settings"]+os.sep+self._config["savedata"]): self.load() # Load configuration if possible
		if False: pass # Loading configuration causes more problems than it solves.
		else:
			self.debug("Configuration initiated ...")
			for key in ("name","nick","host"):
				if key not in data:
					return self
			for key in self._config.keys():
				if key in data: self._config[key] = data[key]
			self._config["ready"] = True
			self.debug("Configuration completed successfully.")
		return self

	def debug(self, data):

		debug_text = time.strftime("%d-%b-%Y %H:%M:%S",time.localtime())+" "+self._config["host"]+":"+str(self._config["port"])+" : "+data+"\n"
		debug_mode = 1
		if debug_mode==1:
			# open("debug.txt","w").write(debug_text)
			self._debug_fh.write(debug_text)
		if debug_mode == 2:
			sys.stdout.write(debug_text)


	def disconnect(self): # Terminate all child threads of this object before disconnecting from the hub.
		# self._debug = lambda s: sys.stdout.write(s+"\n") # NOTICE : Debugging purposes
		self.debug("Terminating all searches ...")
		for item in self._search: # Terminate all searches
			if self._search[item]["socket"] is not None and self._search[item]["socket"].active():
				self._search[item]["socket"].close()
		self.debug("Terminating all transfers ...")
		# for transfer in self._transfer: # Terminate all transfers spawned
		# 	if transfer["socket"].active():
		# 		transfer["socket"].close()
		self.debug("Terminating download manager thread ...")
		self._download["active"] = False
		# if self._download["thread"] is not None:
		# 	self._download["thread"].join()
		self.debug("Terminating step thread ...")
		self._step["active"] = False
		# if self._step["thread"] is not None:
		# 	self._step["thread"].join() # Terminate step thread
		# self._step["thread"] = None
		self.debug("Terminating connection to server ...")
		if self._socket is not None:
			self._socket.close() # Terminate connection to server
		self.debug("Disconnected from Hub.")
		
		return self

	def cli(self): # Provide a Command Line Interface for testing purposes before the GUI can be built
		"Provides a Command Line Interface for the Direct Connect Client."
		print "Command Line Interface"
		while True:
			try:
				x = raw_input()
				if x=="!configure":
					print "Enter the Client Name              : ",; name = raw_input()
					print "Enter the Hub Address              : ",; host = raw_input()
					print "Enter the Nickname you wish to use : ",; nick = raw_input()
					print "Enter the Password you wish to use : ",; _pass = raw_input()
					self.configure({"name":name, "host":host, "nick":nick, "pass":_pass});
					# This module allows you to configure the dc search program.
				if x=="!connect": self.connect()
				if x=="!disconnect": self.disconnect()
				if x=="!status": print "Connection Status : "+("mode" if self._socket.active() else "Inactive")
				if x=="!nicklist":
					for nick in self._config["nicklist"]: print nick, self._config["nicklist"][nick]
				if x=="!exit":
					self.disconnect()
					self._debug_fh.close()
					break
				#  Delete all invalid searches
				if len(x)>0 and x[0]=="?": self.search(x[1:],{"display":sys.stdout})
				if len(x)>0 and x[0]==":": self.mc_send(x[1:])
				if len(x)>0 and x[0]=="@": self.pm_send(x[1:].split()[0]," ".join(x.split()[1:]) )
				if len(x)>0 and x[0]=="~": exec (x[1:])
				if len(x)>0 and x[0]=="$": self._socket.send(x[1:])
				if len(x)>0 and x[0]=="^": self.download_tth("XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX")
				if len(x)>0 and x[0]=="&": print [item["part"] for item in self._queue]
				if len(x)>0 and x[0]=="*":
					for t in sorted([t.name for t in threading.enumerate()]): print "THREAD :: "+t
			except KeyboardInterrupt: exit()
			except Exception as e: print e
		return self
		
if __name__=="__main__":
	temp_nick = ''.join(random.SystemRandom().choice(string.ascii_uppercase + string.digits) for _ in range(10))
	data = { "mode":True, "name":"pyDC", "host":"10.109.61.61","nick":temp_nick,"pass":"password","desc":"","email":"","sharesize":1073741824,"localhost":"127.0.0.1","overwrite":True}
	x = search_client().configure(data).connect();
	x.cli();