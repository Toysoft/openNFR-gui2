from Screens.InfoBar import InfoBar
from Screens.Screen import Screen
from Screens.Standby import TryQuitMainloop
from Screens.MessageBox import MessageBox
from Components.ActionMap import ActionMap
from Components.ConfigList import ConfigListScreen
from Components.Label import Label
from Components.Sources.StaticText import StaticText
from Components import Harddisk
from os import path, listdir, system, makedirs
import re

class MultiBootStartup(ConfigListScreen, Screen):

	skin = """
	<screen name="MultiBootStartup" position="center,center" size="500,250"  flags="wfNoBorder" title="MultiBoot STARTUP Selector" backgroundColor="transparent">
		<eLabel name="b" position="0,0" size="500,250" backgroundColor="#00ffffff" zPosition="-2" />
		<eLabel name="a" position="1,1" size="498,248" backgroundColor="#00000000" zPosition="-1" />
		<widget source="Title" render="Label" position="10,10" foregroundColor="#00ffffff" size="480,50" halign="center" font="Regular; 35" backgroundColor="#00000000" />
		<eLabel name="line" position="1,69" size="498,1" backgroundColor="#00ffffff" zPosition="1" />
		<widget source="config" render="Label" position="10,90" size="480,90" halign="center" font="Regular; 30" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<widget source="key_red" render="Label" position="35,212" size="170,30" noWrap="1" zPosition="1" valign="center" font="Regular; 20" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<widget source="key_green" render="Label" position="228,212" size="170,30" noWrap="1" zPosition="1" valign="center" font="Regular; 20" halign="left" backgroundColor="#00000000" foregroundColor="#00ffffff" />
		<eLabel position="25,209" size="6,40" backgroundColor="#00e61700" />
		<eLabel position="216,209" size="6,40" backgroundColor="#0061e500" />
	</screen>
	"""

	def __init__(self, session):
		Screen.__init__(self, session)
		self.title = _("MultiBoot Selector")

		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText(_("Save"))
		self["config"] = StaticText(_("Select Image: STARTUP_1"))
		self.selection = 0
		self.list = self.list_files("/boot")
		self.getImageInformation()

		self.startup()

		self["actions"] = ActionMap(["WizardActions", "SetupActions", "ColorActions"],
		{
			"left": self.left,
			"right": self.right,
			"green": self.save,
			"red": self.cancel,
			"cancel": self.cancel,
			"ok": self.save,
		}, -2)

		self.onLayoutFinish.append(self.layoutFinished)
		
	def getImageInformation(self):
		self.friendlylist = []
		makedirs("/tmp/boot")
		for name in self.list:
			device = self.read_startup("/boot/" + name).split("=",1)[1].split(" ",1)[0]
			system("mount %s /tmp/boot" % device)
			version = self.searchString("/tmp/boot/etc/image-version", "^version=")
			creator = self.searchString("/tmp/boot/etc/image-version", "^creator=")
			build = self.searchString("/tmp/boot/etc/image-version", "^build=")
			system("umount /tmp/boot && ls /tmp/boot")
			self.friendlylist.append("%s %s %s" % (creator,version,build))
		system("rmdir /tmp/boot && ls /tmp")

	def searchString(self, file, search):
		f = open(file)
		for line in f:
			if re.match(search, line):
				return line.split("=")[1].replace('\n', '')
		f.close()

	def layoutFinished(self):
		self.setTitle(self.title)

	def createSummary(self):
		from Screens.SimpleSummary import SimpleSummary
		return SimpleSummary

	def startup(self):
		self["config"].setText(_("Select Image: %s %s") % (self.list[self.selection],self.friendlylist[self.selection] ))

	def save(self):
		print "[MultiBootStartup] select new startup: ", self.list[self.selection]
		system("cp -f /boot/%s /boot/STARTUP"%self.list[self.selection])
		restartbox = self.session.openWithCallback(self.restartBOX,MessageBox,_("Do you want to reboot now with selected image?"), MessageBox.TYPE_YESNO)

	def cancel(self):
		self.close()

	def left(self):
		self.selection = self.selection - 1
		if self.selection == -1:
			self.selection = len(self.list) - 1
		self.startup()

	def right(self):
		self.selection = self.selection + 1
		if self.selection == len(self.list):
			self.selection = 0
		self.startup()

	def read_startup(self, FILE):
		self.file = FILE
		with open(self.file, 'r') as myfile:
			data=myfile.read().replace('\n', '')
		myfile.close()
		return data

	def list_files(self, PATH):
		files = []
		self.path = PATH
		for name in listdir(self.path):
			if path.isfile(path.join(self.path, name)):
				cmdline = self.read_startup("/boot/" + name).split("=",1)[1].split(" ",1)[0]
				if cmdline in Harddisk.getextdevices("ext4") and not name == "STARTUP":
					files.append(name)
		return files

	def restartBOX(self, answer):
		if answer is True:
			self.session.open(TryQuitMainloop, 2)
		else:
			self.close()
