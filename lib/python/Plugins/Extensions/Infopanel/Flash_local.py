from Plugins.SystemPlugins.Hotplug.plugin import hotplugNotifier
from Plugins.Extensions.NFR4XBoot.plugin import *
from Components.Button import Button
from Components.Label import Label
from Components.ActionMap import ActionMap
from Components.MenuList import MenuList
from Components.FileList import FileList
from Components.Task import Task, Job, job_manager, Condition
from Components.Sources.StaticText import StaticText
from Components.ProgressBar import ProgressBar
from Components.SystemInfo import SystemInfo
from Components.Input import Input
from Screens.Console import Console
from Screens.MessageBox import MessageBox
from Screens.ChoiceBox import ChoiceBox
from Screens.Screen import Screen
from Screens.HelpMenu import HelpableScreen
from Screens.TaskView import JobView
from Tools.Downloader import downloadWithProgress
from Tools.LoadPixmap import LoadPixmap
from Tools.Directories import fileExists
from skin import parseColor
from enigma import fbClass
import urllib2
import os
import shutil
import math
from boxbranding import getBoxType,  getImageDistro, getMachineName, getMachineBuild, getMachineBrand, getBrandOEM, getImageVersion, getMachineKernelFile, getMachineRootFile, getMachineMtdKernel, getMachineMtdRoot
distro =  getImageDistro()
ImageVersion = getImageVersion()
ROOTFSBIN = getMachineRootFile()
KERNELBIN = getMachineKernelFile()
MTDKERNEL = getMachineMtdKernel()
MTDROOTFS = getMachineMtdRoot()

#############################################################################################################
image = 0 # 0=openNFR
if distro.lower() == "opennfr":
	image = 0
if getBrandOEM() == "fulan":
	feedurl_nfr = 'http://dev.nachtfalke.biz/nfr/feeds/%s/images' %ImageVersion
else:
	feedurl_nfr = 'http://dev.nachtfalke.biz/nfr/feeds/%s/images' %ImageVersion
	
imagePath = '/media/hdd/images'
flashPath = '/media/hdd/images/flash'
flashTmp = '/media/hdd/images/tmp'
ofgwritePath = '/usr/bin/ofgwrite'
strPath = ''
filename = ''
#############################################################################################################

def Freespace(dev):
	statdev = os.statvfs(dev)
	space = (statdev.f_bavail * statdev.f_frsize) / 1024
	print "[Flash Online] Free space on %s = %i kilobytes" %(dev, space)
	return space

def ReadNewfeed():
	f = open('/etc/enigma2/newfeed', 'r')
	newfeed = f.readlines()
	f.close()
	return newfeed

class FlashOnline(Screen):
	skin = """
	<screen position="center,center" size="560,400" title="Flash On the Fly">
		<ePixmap position="0,360"   zPosition="1" size="140,40" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/Infopanel/pics/red.png" transparent="1" alphatest="on" />
		<ePixmap position="140,360" zPosition="1" size="140,40" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/Infopanel/pics/green.png" transparent="1" alphatest="on" />
		<ePixmap position="280,360" zPosition="1" size="140,40" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/Infopanel/pics/yellow.png" transparent="1" alphatest="on" />
		<ePixmap position="420,360" zPosition="1" size="140,40" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/Infopanel/pics/blue.png" transparent="1" alphatest="on" />
		<widget name="key_red" position="0,360" zPosition="2" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
		<widget name="key_green" position="140,360" zPosition="2" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
		<widget name="key_yellow" position="280,360" zPosition="2" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
		<widget name="key_blue" position="420,360" zPosition="2" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
		<widget name="info-online" position="10,30" zPosition="1" size="450,100" font="Regular;20" halign="left" valign="top" transparent="1" />
		<widget name="info-local" position="10,150" zPosition="1" size="450,200" font="Regular;20" halign="left" valign="top" transparent="1" />
	</screen>"""
		
	def __init__(self, session):
		Screen.__init__(self, session)
		self.session = session
		self.selection = 0
		if getMachineBuild() in ("hd51","vs1500","h7","8100s"):
			self.devrootfs = "/dev/mmcblk0p3"
		elif getMachineBuild() in ("gb7252"):
			self.devrootfs = "/dev/mmcblk0p4"
		else:
			self.devrootfs = "/dev/mmcblk1p3"
		self.multi = 1
		self.list = self.list_files("/boot")
		self.MTDKERNEL = getMachineMtdKernel()
		self.MTDROOTFS = getMachineMtdRoot()
		
		Screen.setTitle(self, _("Flash On the Fly"))
		if SystemInfo["HaveMultiBoot"]:
			self["key_yellow"] = Button(_("STARTUP"))
			self.read_current_multiboot()
		else:
			self["key_yellow"] = Button("")
		self["key_green"] = Button("Online")
		self["key_red"] = Button(_("Exit"))
		self["key_blue"] = Button("Local")
		self["info-local"] = Label(_("Local = Flash a image from local path /hdd/images"))
		self["info-online"] = Label(_("Online = Download a image and flash it"))
		
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], 
		{
			"blue": self.blue,
			"yellow": self.yellow,
			"green": self.green,
			"red": self.quit,
			"cancel": self.quit,
		}, -2)
		if SystemInfo["HaveMultiBoot"]:
			if getMachineBuild() in ("gb7252"):
				self.multi = self.read_startup("/boot/" + self.list[self.selection]).split(".",1)[1].split(":",1)[0]
				self.multi = self.multi[-1:]
			else:
				self.multi = self.read_startup("/boot/" + self.list[self.selection]).split(".",1)[1].split(" ",1)[0]
				self.multi = self.multi[-1:]
			print "[Flash Online] MULTI:",self.multi

	def check_hdd(self):
		if os.path.exists("/media/nfr4xboot"):
			message = _('NFR4XBoot is still installed!\nNow removing NFR4XBoot and reboot the box. After reboot FlashLocal is available.\nYour installed images are not deleted and available after re-installing NFR4XBoot again.')
			ybox = self.session.openWithCallback(self.removenfrxboot, MessageBox, message, MessageBox.TYPE_YESNO)
			ybox.setTitle(_('Remove NFR4XBoot'))
			return False
		if not os.path.exists("/media/hdd"):
			self.session.open(MessageBox, _("No /hdd found !!\nPlease make sure you have a HDD mounted.\n\nExit plugin."), type = MessageBox.TYPE_ERROR)
			return False
		if Freespace('/media/hdd') < 300000:
			self.session.open(MessageBox, _("Not enough free space on /hdd !!\nYou need at least 300Mb free space.\n\nExit plugin."), type = MessageBox.TYPE_ERROR)
			return False
		if not os.path.exists(ofgwritePath):
			self.session.open(MessageBox, _('ofgwrite not found !!\nPlease make sure you have ofgwrite installed in /usr/bin/ofgwrite.\n\nExit plugin.'), type = MessageBox.TYPE_ERROR)
			return False

		if not os.path.exists(imagePath):
			try:
				os.mkdir(imagePath)
			except:
				pass
		
		if os.path.exists(flashPath):
			try:
				os.system('rm -rf ' + flashPath)
			except:
				pass
		try:
			os.mkdir(flashPath)
		except:
			pass
		return True
	
	def removenfrxboot(self, yesno):
		if yesno:
			f = file('/etc/fstab','r')
			lines = f.readlines()
			f.close()
			for line in lines:
				if "/media/nfr4xboot" in line:
					lines.remove(line)
			os.system("rm /etc/fstab")
			f = file('/etc/fstab','w')  
			for l in lines:
				f.write(l)
			f.close()
			os.system('rm /sbin/nfr4xinit')
			os.system('rm /sbin/init')
			os.system('ln -sfn /sbin/init.sysvinit /sbin/init')
			os.system('chmod 777 /sbin/init')
			os.system('mv /etc/init.d/volatile-media.sh.back /etc/init.d/volatile-media.sh')
			os.system('rm /media/nfr4xboot/NFR4XBootI/.nfr4xboot')
			os.system('rm /media/nfr4xboot/NFR4XBootI/.Flash')
			os.system('rm /usr/lib/enigma2/python/Plugins/Extensions/NFR4XBoot/.nfr4xboot_location')
			os.system('reboot -p')
		else:
			return
            
	def quit(self):
		self.close()	
		
	def blue(self):
		if self.check_hdd():
			self.session.open(doFlashImage, online = False, list=self.list[self.selection], multi=self.multi, devrootfs=self.devrootfs, mtdkernel=self.MTDKERNEL, mtdrootfs=self.MTDROOTFS)
		else:
			self.close()

	def green(self):
		if self.check_hdd():
			self.session.open(doFlashImage, online = True, list=self.list[self.selection], multi=self.multi, devrootfs=self.devrootfs, mtdkernel=self.MTDKERNEL, mtdrootfs=self.MTDROOTFS)
		else:
			self.close()
	def yellow(self):
		if SystemInfo["HaveMultiBoot"]:
			self.selection = self.selection + 1
			if self.selection == len(self.list):
				self.selection = 0
			self["key_yellow"].setText(_(self.list[self.selection]))
			if getMachineBuild() in ("gb7252"):
				self.multi = self.read_startup("/boot/" + self.list[self.selection]).split(".",1)[1].split(":",1)[0]
				self.multi = self.multi[-1:]
			else:
				self.multi = self.read_startup("/boot/" + self.list[self.selection]).split(".",1)[1].split(" ",1)[0]
				self.multi = self.multi[-1:]
			print "[Flash Online] MULTI:",self.multi
			self.devrootfs = self.find_rootfs_dev(self.list[self.selection])
			print "[Flash Online] MULTI rootfs ", self.devrootfs
			
			self.read_current_multiboot()
	def read_current_multiboot(self):
		if getMachineBuild() in ("hd51","vs1500","h7"):
			if self.list[self.selection] == "Recovery":
				cmdline = self.read_startup("/boot/STARTUP").split("=",3)[3].split(" ",1)[0]
			else:
				cmdline = self.read_startup("/boot/" + self.list[self.selection]).split("=",3)[3].split(" ",1)[0]
		elif getMachineBuild() in ("8100s"):
			if self.list[self.selection] == "Recovery":
				cmdline = self.read_startup("/boot/STARTUP").split("=",4)[4].split(" ",1)[0]
			else:
				cmdline = self.read_startup("/boot/" + self.list[self.selection]).split("=",4)[4].split(" ",1)[0]
		elif getMachineBuild() in ("cc1","sf8008"):
			if self.list[self.selection] == "Recovery":
				cmdline = self.read_startup("/boot/STARTUP").split("=",1)[1].split(" ",1)[0]
			else:
				cmdline = self.read_startup("/boot/" + self.list[self.selection]).split("=",1)[1].split(" ",1)[0]
		else:
			if self.list[self.selection] == "Recovery":
				cmdline = self.read_startup("/boot/cmdline.txt").split("=",1)[1].split(" ",1)[0]
			else:
				cmdline = self.read_startup("/boot/" + self.list[self.selection]).split("=",1)[1].split(" ",1)[0]
		cmdline = cmdline.lstrip("/dev/")
		self.MTDROOTFS = cmdline
		self.MTDKERNEL = cmdline[:-1] + str(int(cmdline[-1:]) -1)
		print "[Flash Online] kernel device: ",self.MTDKERNEL
		print "[Flash Online] rootfsdevice: ",self.MTDROOTFS

	def read_startup(self, FILE):
		file = FILE
		with open(file, 'r') as myfile:
			data=myfile.read().replace('\n', '')
		myfile.close()
		return data
		
	def find_rootfs_dev(self, file):
		startup_content = self.read_startup("/boot/" + file)
		return startup_content[startup_content.find("root=")+5:].split()[0]

	def list_files(self, PATH):
		files = []
		if SystemInfo["HaveMultiBoot"]:
			path = PATH
			if getMachineBuild() in ("hd51","vs1500","h7","8100s","gb7252","cc1","sf8008"):
				for name in os.listdir(path):
					if name != 'bootname' and os.path.isfile(os.path.join(path, name)):
						try:
							cmdline = self.find_rootfs_dev(name)
						except IndexError:
							continue
						cmdline_startup = self.find_rootfs_dev("STARTUP")
						if (cmdline != cmdline_startup) and (name != "STARTUP"):
							files.append(name)
				files.insert(0,"STARTUP")
			else:
				for name in os.listdir(path):
					if name != 'bootname' and os.path.isfile(os.path.join(path, name)):
						try:
							cmdline = self.read_startup("/boot/" + name).split("=",1)[1].split(" ",1)[0]
						except IndexError:
							continue
						cmdline_startup = self.read_startup("/boot/cmdline.txt").split("=",1)[1].split(" ",1)[0]
						if (cmdline != cmdline_startup) and (name != "cmdline.txt"):
							files.append(name)
     				files.insert(0,"cmdline.txt")
		else:
			files = "None"
		return files
			
class doFlashImage(Screen):
	skin = """
	<screen position="center,center" size="560,500" title="Flash On the fly (select a image)">
		<ePixmap position="0,460"   zPosition="1" size="140,40" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/Infopanel/pics/red.png" transparent="1" alphatest="on" />
		<ePixmap position="140,460" zPosition="1" size="140,40" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/Infopanel/pics/green.png" transparent="1" alphatest="on" />
		<ePixmap position="280,460" zPosition="1" size="140,40" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/Infopanel/pics/yellow.png" transparent="1" alphatest="on" />
		<ePixmap position="420,460" zPosition="1" size="140,40" pixmap="/usr/lib/enigma2/python/Plugins/Extensions/Infopanel/pics/buttons/blue.png" transparent="1" alphatest="on" />
		<widget name="key_red" position="0,460" zPosition="2" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
		<widget name="key_green" position="140,460" zPosition="2" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
		<widget name="key_yellow" position="280,460" zPosition="2" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
		<widget name="key_blue" position="420,460" zPosition="2" size="140,40" valign="center" halign="center" font="Regular;21" transparent="1" shadowColor="black" shadowOffset="-1,-1" />
		<widget name="imageList" position="10,10" zPosition="1" size="450,450" font="Regular;20" scrollbarMode="showOnDemand" transparent="1" />
	</screen>"""
		
	def __init__(self, session, online, list=None, multi=None, devrootfs=None, mtdkernel=None, mtdrootfs=None ):
		Screen.__init__(self, session)
		self.session = session

		Screen.setTitle(self, _("Flash On the fly (select a image)"))
		self["key_green"] = Button(_("Flash"))
		self["key_red"] = Button(_("Exit"))
		self["key_blue"] = Button("")
		self["key_yellow"] = Button("")
		self.filename = None
		self.strPath = None
		self.imagelist = []
		self.simulate = False
		self.Online = online
		self.List = list
		self.multi=multi
		self.devrootfs=devrootfs
		self.MTDKERNEL = mtdkernel
		self.MTDROOTFS = mtdrootfs
		self.imagePath = imagePath
		self.feedurl = feedurl_nfr
		if image == 0:
			self.feed = "nfr"
		self["imageList"] = MenuList(self.imagelist)
		self["actions"] = ActionMap(["OkCancelActions", "ColorActions"], 
		{
			"green": self.green,
			"ok": self.green,
			"yellow": self.yellow,
			"red": self.quit,
			"blue": self.blue,
			"cancel": self.quit,
		}, -2)
		self.onLayoutFinish.append(self.layoutFinished)
		self.newfeed = None
		if os.path.exists('/etc/enigma2/newfeed'):
			self.newfeed = ReadNewfeed()

		
	def quit(self):
	        if self.simulate or not self.List == "STARTUP":
			fbClass.getInstance().unlock()
		self.close()	
		
	def blue(self):
		if self.Online:
			if image == 0:
				self.feed = "nfr"
				self.layoutFinished()
			return
		sel = self["imageList"].l.getCurrentSelection()
		if sel == None:
			print"Nothing to select !!"
			return
		self.filename = sel
		self.session.openWithCallback(self.RemoveCB, MessageBox, _("Do you really want to delete\n%s ?") % (sel), MessageBox.TYPE_YESNO)

	def RemoveCB(self, ret):
		if ret:
			if os.path.exists(self.imagePath + "/" + self.filename):
				os.remove(self.imagePath + "/" + self.filename)
			self.imagelist.remove(self.filename)
			self["imageList"].l.setList(self.imagelist)
		
	def box(self):
		box = getBoxType()
		machinename = getMachineName()
		if box in ('uniboxhd1', 'uniboxhd2', 'uniboxhd3'):
			box = "ventonhdx"
		elif box == 'odinm6':
			box = getMachineName().lower()
		elif box == "inihde" and machinename.lower() == "xpeedlx":
			box = "xpeedlx"
		elif box in ('xpeedlx1', 'xpeedlx2'):
			box = "xpeedlx"
		elif box == "inihde" and machinename.lower() == "hd-1000":
			box = "sezam-1000hd"
		elif box == "ventonhdx" and machinename.lower() == "hd-5000":
			box = "sezam-5000hd"
		elif box == "ventonhdx" and machinename.lower() == "premium twin":
			box = "miraclebox-twin"
		elif box == "xp1000" and machinename.lower() == "sf8 hd":
			box = "sf8"
		##Formuler not tested yet
		elif box == "formuler1" and machinename.lower() == "formuler1":
			box = "formuler1"
		elif box == "formuler3" and machinename.lower() == "formuler3":
			box = "formuler3"
		elif box.startswith('et') and not box in ('et8000', 'et10000'):
			box = box[0:3] + 'x00'
		elif box == 'odinm9' and self.feed == "nfr":
			box = 'maram9'
		elif box == 'bre2ze':
			box = 'ew7362'	
		return box

	def green(self, ret = None):
		sel = self["imageList"].l.getCurrentSelection()
		if sel == None:
			print"Nothing to select !!"
			return
		file_name = self.imagePath + "/" + sel
		self.filename = file_name
		self.sel = sel
		box = self.box()
		self.hide()
		if self.Online:
			url = self.feedurl + "/" + box + "/" + sel
			print "[Flash Online] Download image: >%s<" % url
			if self.newfeed:
				self.feedurl = self.newfeed[0][:-1]
				url = self.feedurl + "/" + box + "/" + sel
				authinfo = urllib2.HTTPPasswordMgrWithDefaultRealm()
				authinfo.add_password(None, self.feedurl, self.newfeed[1][:-1], self.newfeed[2][:-1])
				handler = urllib2.HTTPBasicAuthHandler(authinfo)
				myopener = urllib2.build_opener(handler)
				opened = urllib2.install_opener(myopener)
				u = urllib2.urlopen(url)
				total_size = int(u.info().getheaders("Content-Length")[0])
				downloaded = 0
				CHUNK = 256 * 1024
				with open(file_name, 'wb') as fp:
					while True:
						chunk = u.read(CHUNK)
						downloaded += len(chunk)
						print "Downloading: %s Bytes of %s" % (downloaded, total_size)
						if not chunk: break
						fp.write(chunk)
				self.ImageDownloadCB(False)
			else:
				try:
					u = urllib2.urlopen(url)
					f = open(file_name, 'wb')
					f.close()
					job = ImageDownloadJob(url, file_name, sel)
					job.afterEvent = "close"
					job_manager.AddJob(job)
					job_manager.failed_jobs = []
					self.session.openWithCallback(self.ImageDownloadCB, JobView, job, backgroundable = False, afterEventChangeable = False)
				except urllib2.URLError as e:
					print "[Flash Online] Download failed !!\n%s" % e
					self.session.openWithCallback(self.ImageDownloadCB, MessageBox, _("Download Failed !!" + "\n%s" % e), type = MessageBox.TYPE_ERROR)
					self.close()
		else:
			self.session.openWithCallback(self.startInstallLocal, MessageBox, _("Do you want to backup your settings now?"), default=False)
			

	def ImageDownloadCB(self, ret):
		if ret:
			return
		if job_manager.active_job:
			job_manager.active_job = None
			self.close()
			return
		if len(job_manager.failed_jobs) == 0:
			self.session.openWithCallback(self.SettingsBack, MessageBox, _("Do you want to backup your settings now?"), default=False)
		else:
			self.session.open(MessageBox, _("Download Failed !!"), type = MessageBox.TYPE_ERROR)
			
	def SettingsBack(self, ret):
		if ret:
			from Plugins.SystemPlugins.SoftwareManager.BackupRestore import BackupScreen
			self.flashWithPostFlashActionMode = 'online'
			self.session.openWithCallback(self.flashWithPostFlashAction,BackupScreen, runBackup = True)		
		else:
			self.flashWithPostFlashActionMode = 'online'
			self.flashWithPostFlashAction()
			
	def flashWithPostFlashAction(self, ret = True):
		if ret:
			print "flashWithPostFlashAction"
			title =_("Please select what to do after flashing the image:\n(In addition, if it exists, a local script will be executed as well at /media/hdd/images/config/myrestore.sh)")
			list = ((_("Flash and start installation wizard"), "wizard"),
			(_("Flash and restore settings and no plugins"), "restoresettingsnoplugin"),
			(_("Flash and restore settings and selected plugins (ask user)"), "restoresettings"),
			(_("Flash and restore settings and all saved plugins"), "restoresettingsandallplugins"),
			(_("Do not flash image"), "abort"))
			self.session.openWithCallback(self.postFlashActionCallback, ChoiceBox,title=title,list=list,selection=self.SelectPrevPostFashAction())
		else:
			self.show()

	def SelectPrevPostFashAction(self):
		index = 0
		Settings = False
		AllPlugins = False
		noPlugins = False
		
		if os.path.exists('/media/hdd/images/config/settings'):
			Settings = True
		if os.path.exists('/media/hdd/images/config/plugins'):
			AllPlugins = True
		if os.path.exists('/media/hdd/images/config/noplugins'):
			noPlugins = True

		if 	Settings and noPlugins:
			index = 1
		elif Settings and not AllPlugins and not noPlugins:
			index = 2
		elif Settings and AllPlugins:
			index = 3

		return index

	def postFlashActionCallback(self, answer):
		print "postFlashActionCallback"
		restoreSettings   = False
		restoreAllPlugins = False
		restoreSettingsnoPlugin = False
		if answer is not None:
			if answer[1] == "restoresettings":
				restoreSettings   = True
			if answer[1] == "restoresettingsnoplugin":
				restoreSettings = True
				restoreSettingsnoPlugin = True
			if answer[1] == "restoresettingsandallplugins":
				restoreSettings   = True
				restoreAllPlugins = True
			if restoreSettings:
				self.SaveEPG()
			if answer[1] != "abort":
				if restoreSettings:
					try:
						os.system('mkdir -p /media/hdd/images/config')
						os.system('touch /media/hdd/images/config/settings')
					except:
						print "postFlashActionCallback: failed to create /media/hdd/images/config/settings"
				else:
					if os.path.exists('/media/hdd/images/config/settings'):
						os.system('rm -f /media/hdd/images/config/settings')
				if restoreAllPlugins:
					try:
						os.system('mkdir -p /media/hdd/images/config')
						os.system('touch /media/hdd/images/config/plugins')
					except:
						print "postFlashActionCallback: failed to create /media/hdd/images/config/plugins"
				else:
					if os.path.exists('/media/hdd/images/config/plugins'):
						os.system('rm -f /media/hdd/images/config/plugins')
				if restoreSettingsnoPlugin:
					try:
						os.system('mkdir -p /media/hdd/images/config')
						os.system('touch /media/hdd/images/config/noplugins')
					except:
						print "postFlashActionCallback: failed to create /media/hdd/images/config/noplugins"
				else:
					if os.path.exists('/media/hdd/images/config/noplugins'):
						os.system('rm -f /media/hdd/images/config/noplugins')
				if self.flashWithPostFlashActionMode == 'online':
					self.unzip_image(self.filename, flashPath)
				elif self.flashWithPostFlashActionMode == 'device':
					self.unzip_image(self.filename, flashPath)
				else:
					self.startInstallLocalCB()
			else:
				self.show()
		else:
			self.show()

	def unzip_image(self, filename, path):
		print "Unzip %s to %s" %(filename,path)
		self.session.openWithCallback(self.cmdFinished, Console, title = _("Unzipping files, Please wait ..."), cmdlist = ['unzip ' + filename + ' -o -d ' + path, "sleep 3"], closeOnSuccess = True)

	def cmdFinished(self):
		self.prepair_flashtmp(flashPath)
		self.Start_Flashing()

	def Start_Flashing(self):
		print "Start Flashing"
		cmdlist = []
		#######################fix multiboot###################
		os.system('rm /sbin/init;ln -sfn /sbin/init.sysvinit /sbin/init')		
		if os.path.exists(ofgwritePath):
			text = _("Flashing: ")
			if self.simulate:
				text += _("Simulate (no write)")
				if SystemInfo["HaveMultiBoot"]:
					if getMachineBuild() in ("cc1","sf8008"):
						cmdlist.append("%s -r%s -k%s %s > /dev/null 2>&1" % (ofgwritePath, self.MTDROOTFS, self.MTDKERNEL, flashTmp))
					else:
						cmdlist.append("%s -n -r -k -m%s %s > /dev/null 2>&1" % (ofgwritePath, self.multi, flashTmp))
				elif getMachineBuild() in ("u51","u52","u53","u5","u5pvr","cc1","sf8008"):
 					cmdlist.append("%s -n -r%s -k%s %s > /dev/null 2>&1" % (ofgwritePath, MTDROOTFS, MTDKERNEL, flashTmp))					
				elif getMachineBuild() in ("h9","i55plus","hd60","v8plus"):
					cmdlist.append("%s -n -f -r -k %s > /dev/null 2>&1" % (ofgwritePath, flashTmp))
				else:
					cmdlist.append("%s -n -r -k %s > /dev/null 2>&1" % (ofgwritePath, flashTmp))
				self.close()
				message = "echo -e '\n"
				message += _('Show only found image and mtd partitions.\n')
				message += "'"
			else:
				text += _("root and kernel")
				if SystemInfo["HaveMultiBoot"]:
					if not self.List == "STARTUP":
						os.system('mkfs.ext4 -F ' + self.devrootfs)
					if getMachineBuild() in ("cc1","sf8008"):
						cmdlist.append("%s -r%s -k%s %s > /dev/null 2>&1" % (ofgwritePath, self.MTDROOTFS, self.MTDKERNEL, flashTmp))
					else:
						cmdlist.append("%s -r -k -m%s %s > /dev/null 2>&1" % (ofgwritePath, self.multi, flashTmp))
					if not self.List == "STARTUP":
						cmdlist.append("umount -fl /oldroot_bind")
						cmdlist.append("umount -fl /newroot")
				elif getMachineBuild() in ("u51","u52","u53","u5","u5pvr","cc1","sf8008"):
	 				cmdlist.append("%s -r%s -k%s %s > /dev/null 2>&1" % (ofgwritePath, MTDROOTFS, MTDKERNEL, flashTmp))					
				elif getMachineBuild() in ("h9","i55plus","hd60","v8plus"):
					cmdlist.append("%s -f -r -k %s > /dev/null 2>&1" % (ofgwritePath, flashTmp))
				else:
					cmdlist.append("%s -r -k %s > /dev/null 2>&1" % (ofgwritePath, flashTmp))
				message = "echo -e '\n"
				if not self.List == "STARTUP" and SystemInfo["HaveMultiBoot"]:
					message += _('ofgwrite flashing ready.\n')
					message += _('please press exit to go back to the menu.\n')
				else:
					message += _('ofgwrite will stop enigma2 now to run the flash.\n')
					message += _('Your STB will freeze during the flashing process.\n')
					message += _('Please: DO NOT reboot your STB and turn off the power.\n')
					message += _('The image or kernel will be flashing and auto booted in few minutes.\n')
					if self.box() == 'gb800solo':
						message += _('GB800SOLO takes about 20 mins !!\n')
				message += "'"
			        cmdlist.append(message)
				self.session.open(Console, title = text, cmdlist = cmdlist, finishedCallback = self.quit, closeOnSuccess = False)
				if not self.simulate:
					fbClass.getInstance().lock()
                                if not self.List == "STARTUP":
					self.close()

	def prepair_flashtmp(self, tmpPath):
		if os.path.exists(flashTmp):
			flashTmpold = flashTmp + 'old'
			os.system('mv %s %s' %(flashTmp, flashTmpold))
			os.system('rm -rf %s' %flashTmpold)
		if not os.path.exists(flashTmp):
			os.mkdir(flashTmp)
		kernel = True
		rootfs = True
		
		for path, subdirs, files in os.walk(tmpPath):
			for name in files:
				if name.find('kernel') > -1 and name.endswith('.bin') and kernel:
					binfile = os.path.join(path, name)
					dest = flashTmp + '/%s' %KERNELBIN
					shutil.copyfile(binfile, dest)
					kernel = False
				elif name.find('root') > -1 and (name.endswith('.bin') or name.endswith('.jffs2') or name.endswith('.bz2')) and rootfs:
					binfile = os.path.join(path, name)
					dest = flashTmp + '/%s' %ROOTFSBIN
					shutil.copyfile(binfile, dest)
					rootfs = False
				elif name.find('uImage') > -1 and kernel:
					binfile = os.path.join(path, name)
					dest = flashTmp + '/uImage'
					shutil.copyfile(binfile, dest)
					kernel = False
				elif name.find('e2jffs2') > -1 and name.endswith('.img') and rootfs:
					binfile = os.path.join(path, name)
					dest = flashTmp + '/e2jffs2.img'
					shutil.copyfile(binfile, dest)
					rootfs = False
					
	def yellow(self):
		if not self.Online:
			self.session.openWithCallback(self.DeviceBrowserClosed, DeviceBrowser, None, matchingPattern="^.*\.(zip|bin|jffs2|img)", showDirectories=True, showMountpoints=True, inhibitMounts=["/autofs/sr0/"])
		else:
			from Plugins.SystemPlugins.SoftwareManager.BackupRestore import BackupScreen
			self.session.openWithCallback(self.green,BackupScreen, runBackup = True)

	def startInstallLocal(self, ret = None):
		if ret:
			from Plugins.SystemPlugins.SoftwareManager.BackupRestore import BackupScreen
			self.flashWithPostFlashActionMode = 'local'
			self.session.openWithCallback(self.flashWithPostFlashAction,BackupScreen, runBackup = True)
		else:
			self.flashWithPostFlashActionMode = 'local'
			self.flashWithPostFlashAction()

	def startInstallLocalCB(self, ret = None):
		if self.sel == str(flashTmp):
			self.Start_Flashing()
		else:
			self.unzip_image(self.filename, flashPath)

	def DeviceBrowserClosed(self, path, filename, binorzip):
		if path:
			print path, filename, binorzip
			strPath = str(path)
			if strPath[-1] == '/':
				strPath = strPath[:-1]
			self.imagePath = strPath
			if os.path.exists(flashTmp):
				os.system('rm -rf ' + flashTmp)
			os.mkdir(flashTmp)
			if binorzip == 0:
				for files in os.listdir(self.imagePath):
					if files.endswith(".bin") or files.endswith('.jffs2') or files.endswith('.img'):
						self.prepair_flashtmp(strPath)
						break
				self.Start_Flashing()
			elif binorzip == 1:
				from Plugins.SystemPlugins.SoftwareManager.BackupRestore import BackupScreen
				self.filename = strPath + '/' + filename
				self.strPath = strPath
				self.flashWithPostFlashActionMode = 'device'
				self.session.openWithCallback(self.flashWithPostFlashAction,BackupScreen, runBackup = True)				
			else:
				self.layoutFinished()
	
		else:
			self.imagePath = imagePath
			

	def layoutFinished(self):
		box = self.box()
		self.imagelist = []
		if self.Online:
			self["key_yellow"].setText("")
			if image == 0:
				self.feedurl = feedurl_nfr
				self["key_blue"].setText("Teamimages")
			url = '%s/%s' % (self.feedurl,box)
			req = urllib2.Request(url)
			try:
				response = urllib2.urlopen(req)
			except urllib2.URLError as e:
				print "URL ERROR: %s\n%s" % (e,url)
				self["imageList"].l.setList(self.imagelist)
				return

			try:
				the_page = response.read()

			except urllib2.HTTPError as e:
				print "HTTP download ERROR: %s" % e.code
				return

			lines = the_page.split('\n')
			tt = len(box)
			for line in lines:
				if line.find("<a href='%s/" % box) > -1:
					t = line.find("<a href='%s/" % box)
					if self.feed == "nfr1":
						self.imagelist.append(line[t+tt+10:t+tt+tt+39])
					else:
						self.imagelist.append(line[t+tt+10:t+tt+tt+40])
				else:
					if line.find('<a href="o') > -1:
						t = line.find('<a href="o')
						e = line.find('zip"')
						self.imagelist.append(line[t+9:e+3])

		else:
			self["key_blue"].setText(_("Delete"))
			self["key_yellow"].setText(_("Devices"))
			for name in os.listdir(self.imagePath):
				if name.endswith(".zip"): # and name.find(box) > 1:
					self.imagelist.append(name)
			self.imagelist.sort()
			if os.path.exists(flashTmp):
				for file in os.listdir(flashTmp):
					if file.find(".bin") > -1:
						self.imagelist.insert( 0, str(flashTmp))
						break

		self["imageList"].l.setList(self.imagelist)

	def SaveEPG(self):
		from enigma import eEPGCache
		epgcache = eEPGCache.getInstance()
		epgcache.save()


class ImageDownloadJob(Job):
	def __init__(self, url, filename, file):
		Job.__init__(self, _("Downloading %s" %file))
		ImageDownloadTask(self, url, filename)

class DownloaderPostcondition(Condition):
	def check(self, task):
		return task.returncode == 0

	def getErrorMessage(self, task):
		return self.error_message

class ImageDownloadTask(Task):
	def __init__(self, job, url, path):
		Task.__init__(self, job, _("Downloading"))
		self.postconditions.append(DownloaderPostcondition())
		self.job = job
		self.url = url
		self.path = path
		self.error_message = ""
		self.last_recvbytes = 0
		self.error_message = None
		self.download = None
		self.aborted = False

	def run(self, callback):
		self.callback = callback
		self.download = downloadWithProgress(self.url,self.path)
		self.download.addProgress(self.download_progress)
		self.download.start().addCallback(self.download_finished).addErrback(self.download_failed)
		print "[ImageDownloadTask] downloading", self.url, "to", self.path

	def abort(self):
		print "[ImageDownloadTask] aborting", self.url
		if self.download:
			self.download.stop()
		self.aborted = True

	def download_progress(self, recvbytes, totalbytes):
		if ( recvbytes - self.last_recvbytes  ) > 10000: # anti-flicker
			self.progress = int(100*(float(recvbytes)/float(totalbytes)))
			self.name = _("Downloading") + ' ' + "%d of %d kBytes" % (recvbytes/1024, totalbytes/1024)
			self.last_recvbytes = recvbytes

	def download_failed(self, failure_instance=None, error_message=""):
		self.error_message = error_message
		if error_message == "" and failure_instance is not None:
			self.error_message = failure_instance.getErrorMessage()
		Task.processFinished(self, 1)

	def download_finished(self, string=""):
		if self.aborted:
			self.finish(aborted = True)
		else:
			Task.processFinished(self, 0)

class DeviceBrowser(Screen, HelpableScreen):
	skin = """
		<screen name="DeviceBrowser" position="center,center" size="520,430" >
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/Infopanel/pics/red.png" position="0,0" size="140,40" alphatest="on" />
			<ePixmap pixmap="/usr/lib/enigma2/python/Plugins/Extensions/Infopanel/pics/green.png" position="140,0" size="140,40" alphatest="on" />
			<widget source="key_red" render="Label" position="0,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#9f1313" transparent="1" />
			<widget source="key_green" render="Label" position="140,0" zPosition="1" size="140,40" font="Regular;20" halign="center" valign="center" backgroundColor="#1f771f" transparent="1" />
			<widget source="message" render="Label" position="5,50" size="510,150" font="Regular;16" />
			<widget name="filelist" position="5,210" size="510,220" scrollbarMode="showOnDemand" />
		</screen>"""

	def __init__(self, session, startdir, message="", showDirectories = True, showFiles = True, showMountpoints = True, matchingPattern = "", useServiceRef = False, inhibitDirs = False, inhibitMounts = False, isTop = False, enableWrapAround = False, additionalExtensions = None):
		Screen.__init__(self, session)

		HelpableScreen.__init__(self)
		Screen.setTitle(self, _("Please select medium"))

		self["key_red"] = StaticText(_("Cancel"))
		self["key_green"] = StaticText()
		self["message"] = StaticText(message)

		self.filelist = FileList(startdir, showDirectories = showDirectories, showFiles = showFiles, showMountpoints = showMountpoints, matchingPattern = matchingPattern, useServiceRef = useServiceRef, inhibitDirs = inhibitDirs, inhibitMounts = inhibitMounts, isTop = isTop, enableWrapAround = enableWrapAround, additionalExtensions = additionalExtensions)
		self["filelist"] = self.filelist

		self["FilelistActions"] = ActionMap(["SetupActions", "ColorActions"],
			{
				"green": self.use,
				"red": self.exit,
				"ok": self.ok,
				"cancel": self.exit
			})

		hotplugNotifier.append(self.hotplugCB)
		self.onShown.append(self.updateButton)
		self.onClose.append(self.removeHotplug)

	def hotplugCB(self, dev, action):
		print "[hotplugCB]", dev, action
		self.updateButton()

	def updateButton(self):

		if self["filelist"].getFilename() or self["filelist"].getCurrentDirectory():
			self["key_green"].text = _("Flash")
		else:
			self["key_green"].text = ""

	def removeHotplug(self):
		print "[removeHotplug]"
		hotplugNotifier.remove(self.hotplugCB)

	def ok(self):
		if self.filelist.canDescent():
			if self["filelist"].showMountpoints == True and self["filelist"].showDirectories == False:
				self.use()
			else:
				self.filelist.descent()

	def use(self):
		print "[use]", self["filelist"].getCurrentDirectory(), self["filelist"].getFilename()
		if self["filelist"].getFilename() is not None and self["filelist"].getCurrentDirectory() is not None:
			if self["filelist"].getFilename().endswith(".bin") or self["filelist"].getFilename().endswith(".jffs2"):
				self.close(self["filelist"].getCurrentDirectory(), self["filelist"].getFilename(), 0)
			elif self["filelist"].getFilename().endswith(".zip"):
				self.close(self["filelist"].getCurrentDirectory(), self["filelist"].getFilename(), 1)
			else:
				return

	def exit(self):
		self.close(False, False, -1)
