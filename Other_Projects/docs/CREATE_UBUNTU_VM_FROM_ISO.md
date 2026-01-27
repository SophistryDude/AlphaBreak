# Create Ubuntu VM from ISO File - Complete Guide

You have an Ubuntu ISO (disk image) but no VM yet. Here's how to create one.

---

## 🔍 What's Happening

**Current Situation:**
- You have: `ubuntu-XX.XX-desktop-amd64.iso` (disk image file)
- Windows is auto-mounting it as DVD drive (D:)
- You DON'T have a virtual machine yet - just the installer

**What you need to do:**
- Create a VirtualBox VM
- Use the ISO to install Ubuntu inside the VM
- Then eject the ISO

**Think of it like:**
- ISO = Installation DVD for Ubuntu
- You need to create a "virtual computer" and install Ubuntu on it

---

## 🚀 Create Ubuntu VM - Complete Guide

### Prerequisites

**What you need:**
- ✅ VirtualBox installed
- ✅ Ubuntu ISO file (you have this - the D: drive)
- ✅ 25+ GB free disk space
- ✅ 30-45 minutes

**Find your ISO file location:**
1. Right-click on D: drive (Ubuntu) in File Explorer
2. Click **Properties**
3. Look at **Location** field
4. Example: `C:\Users\nicho\Downloads\ubuntu-22.04.3-desktop-amd64.iso`
5. **Write this down** - you'll need it

---

## 📋 Step-by-Step: Create Ubuntu VM

### Phase 1: Create the Virtual Machine (5 minutes)

**Step 1: Open VirtualBox**
1. Press **Windows + S**
2. Type: `VirtualBox`
3. Click **Oracle VM VirtualBox**

---

**Step 2: Create New VM**
1. Click **New** button (blue icon, top left)
2. A wizard appears

---

**Step 3: Name and Operating System**
Fill in:
- **Name:** `Ubuntu` (or whatever you want)
- **Folder:** Leave default (C:\Users\nicho\VirtualBox VMs)
- **Type:** `Linux`
- **Version:** `Ubuntu (64-bit)` ⚠️ IMPORTANT: Must be 64-bit

**If you only see "Ubuntu (32-bit)":**
- STOP - Virtualization is disabled in BIOS
- See **Troubleshooting Section** below

Click **Next**

---

**Step 4: Memory Size (RAM)**
- **Recommended:** 4096 MB (4 GB)
- **Minimum:** 2048 MB (2 GB)
- **If you have 16+ GB total RAM:** Use 8192 MB (8 GB)

**Rule:** Don't use more than 50% of your total RAM

Move the slider or type the number

Click **Next**

---

**Step 5: Hard Disk**
Select: **"Create a virtual hard disk now"**

Click **Create**

---

**Step 6: Hard Disk File Type**
Select: **VDI (VirtualBox Disk Image)**

Click **Next**

---

**Step 7: Storage on Physical Hard Disk**
Select: **Dynamically allocated** (recommended)

**Why:** Starts small, grows as needed (saves space)

Click **Next**

---

**Step 8: File Location and Size**
- **Name:** Leave default (`Ubuntu`)
- **Size:**
  - **Minimum:** 25 GB
  - **Recommended:** 50 GB
  - **If you have space:** 100 GB

**Note:** With dynamic allocation, it starts at ~10 GB and grows

Click **Create**

---

**Result:** VM created! You'll see it in VirtualBox Manager (powered off)

---

### Phase 2: Configure VM Settings (5 minutes)

**Step 9: Open Settings**
1. Select your Ubuntu VM (click on it once)
2. Click **Settings** button (gear icon)

---

**Step 10: System Settings**
1. Click **System** in left sidebar
2. Go to **Motherboard** tab:
   - **Boot Order:** Check CD/DVD and Hard Disk, uncheck Floppy
   - Move CD/DVD to top (drag it up)
3. Go to **Processor** tab:
   - **Processor(s):** Set to 2 (or 4 if you have 8+ cores)
   - Check **Enable PAE/NX**

---

**Step 11: Display Settings**
1. Click **Display** in left sidebar
2. Go to **Screen** tab:
   - **Video Memory:** Drag to **128 MB** (max)
   - **Graphics Controller:** VMSVGA
   - Check **Enable 3D Acceleration** (optional, can help performance)

---

**Step 12: Storage - Attach the ISO**
**⚠️ MOST IMPORTANT STEP**

1. Click **Storage** in left sidebar
2. You'll see:
   - **Controller: IDE** (or SATA)
     - 💿 Empty (this is the virtual DVD drive)
   - **Controller: SATA** (or IDE)
     - 💾 Ubuntu.vdi (this is your virtual hard disk)

3. Click on the **💿 Empty** (DVD icon)
4. On the right side, you'll see **Optical Drive:** with a dropdown
5. Click the **small DVD icon** next to dropdown
6. Select **Choose a disk file...**
7. Navigate to your Ubuntu ISO file
   - Example: `C:\Users\nicho\Downloads\ubuntu-22.04.3-desktop-amd64.iso`
8. Select it, click **Open**
9. The DVD should now show the ISO filename instead of "Empty"

---

**Step 13: Network Settings** (Optional but Recommended)
1. Click **Network** in left sidebar
2. **Adapter 1** tab:
   - **Attached to:** NAT (default, usually fine)
   - OR change to **Bridged Adapter** if you want VM to be on same network as your PC

Leave as NAT for now (simpler)

---

**Step 14: Shared Clipboard** (Optional but Nice)
1. Click **General** in left sidebar
2. Go to **Advanced** tab:
   - **Shared Clipboard:** Bidirectional
   - **Drag'n'Drop:** Bidirectional

**Note:** May not work until you install Guest Additions later

---

**Step 15: Apply Settings**
Click **OK** at bottom

---

### Phase 3: Install Ubuntu (30 minutes)

**Step 16: Start the VM**
1. Make sure Ubuntu VM is selected
2. Click **Start** button (green arrow)
3. A new window opens (this is your virtual computer screen)

---

**Step 17: Boot from ISO**
You should see:
- VirtualBox logo
- Then Ubuntu loading screen (purple with dots)
- Then "Try Ubuntu" or "Install Ubuntu" options

**If you see black screen or errors:**
- See **Troubleshooting** section below

---

**Step 18: Ubuntu Installer**

**Welcome Screen:**
- Language: **English** (or your preference)
- Click **Install Ubuntu**

---

**Keyboard Layout:**
- **English (US)** (or your preference)
- Click **Continue**

---

**Updates and Other Software:**
- Select: **Normal installation**
- Check: ☑️ **Download updates while installing Ubuntu**
- Check: ☑️ **Install third-party software for graphics and Wi-Fi hardware**
- Click **Continue**

---

**Installation Type:**
- Select: **Erase disk and install Ubuntu**

**⚠️ DON'T PANIC:** This only affects the VIRTUAL hard disk, not your real Windows PC

- Click **Install Now**
- Popup: "Write changes to disk?" → Click **Continue**

---

**Where are you?**
- Select your timezone (map or dropdown)
- Click **Continue**

---

**Who are you?**
Fill in:
- **Your name:** Nicholas (or whatever)
- **Computer's name:** ubuntu (auto-fills)
- **Username:** nicho (or whatever you want)
- **Password:** [choose a password - REMEMBER THIS!]
- **Confirm password:** [same password]
- Select: **Require my password to log in** (recommended)

Click **Continue**

---

**Step 19: Wait for Installation**
- Ubuntu installs (15-25 minutes)
- Progress bar shows: copying files, installing packages, etc.
- You can minimize the window and do other stuff

**When done:**
- Popup: "Installation Complete"
- Click **Restart Now**

---

**Step 20: Remove Installation Medium**
You'll see message: "Please remove installation medium, then press ENTER"

**Option 1 (Automatic):**
- Just press **ENTER** - VirtualBox usually auto-ejects the ISO

**Option 2 (Manual if needed):**
1. In VirtualBox window menu bar: **Devices** → **Optical Drives**
2. Uncheck the ISO file (or click "Remove disk from virtual drive")
3. Press **ENTER** in the VM window

VM reboots

---

**Step 21: First Boot**
- Ubuntu loads (purple screen, then login screen)
- Login screen appears
- Click your username
- Enter password
- Press **Enter**

**Welcome to Ubuntu!** 🎉

---

### Phase 4: Post-Installation (10 minutes)

**Step 22: Initial Setup Wizard**
Ubuntu shows welcome screens:
- **Livepatch:** Skip (click Next)
- **Help improve Ubuntu:** Choose Yes/No (your preference)
- **Privacy:** Choose settings (default is fine)
- **Ready to go:** Click **Done**

---

**Step 23: Install VirtualBox Guest Additions** (IMPORTANT)

**What it does:**
- Better screen resolution (full screen, auto-resize)
- Shared clipboard (copy/paste between Windows and Ubuntu)
- Shared folders
- Better performance

**How to install:**

1. In VirtualBox window menu bar: **Devices** → **Insert Guest Additions CD image...**
2. Ubuntu shows popup: "Software on this disc..." → Click **Run**
3. Enter your Ubuntu password
4. Terminal window opens, runs installation
5. Wait for "Press Return to close this window"
6. Press **Enter**
7. **Restart Ubuntu:**
   - Click top-right corner (power icon)
   - Select **Restart**
   - Wait for reboot

**After restart:**
- Window should resize properly
- Can go full screen (Right Ctrl + F)
- Can copy/paste between Windows and Ubuntu

---

**Step 24: Update Ubuntu**
1. Click **Show Applications** (bottom-left, 9 dots icon)
2. Type: `Software Updater`
3. Click **Software Updater** app
4. If updates available, click **Install Now**
5. Enter password if prompted
6. Wait for updates (5-10 minutes)
7. Restart if prompted

---

**Step 25: (Optional) Set Up Shared Folder**

**To share files between Windows and Ubuntu:**

1. **In VirtualBox Manager** (with VM powered off):
   - Select Ubuntu VM → Settings
   - Click **Shared Folders**
   - Click folder+ icon (add new shared folder)
   - **Folder Path:** Click dropdown → **Other** → Browse to Windows folder
     - Example: `C:\Users\nicho\Desktop`
   - **Folder Name:** Desktop (or whatever)
   - Check: ☑️ **Auto-mount**
   - Check: ☑️ **Make Permanent**
   - Click **OK** → **OK**

2. **Start Ubuntu VM**

3. **In Ubuntu terminal** (Ctrl+Alt+T):
```bash
sudo adduser $USER vboxsf
```
Enter password, then restart Ubuntu

4. **After restart:**
   - Shared folder appears at `/media/sf_Desktop/`
   - Or in Files app: left sidebar under "Devices"

---

## ✅ Success Checklist

Your Ubuntu VM is ready when:
- [ ] VM boots to Ubuntu login screen
- [ ] Can log in with your password
- [ ] Screen resolution adjusts when you resize window
- [ ] Can copy/paste between Windows and Ubuntu
- [ ] Can open Firefox and browse internet
- [ ] Updates are installed

---

## 🚨 Troubleshooting

### Problem 1: Only See "Ubuntu (32-bit)", No 64-bit Option

**Cause:** Virtualization disabled in BIOS

**Fix:**
1. Restart PC
2. Enter BIOS (press F2, Del, F12, or F10 during boot - depends on motherboard)
3. Find setting called:
   - **Intel VT-x** (Intel CPUs)
   - **AMD-V** (AMD CPUs)
   - **Virtualization Technology**
   - **SVM Mode**
4. Enable it
5. Save and Exit BIOS
6. Boot back to Windows
7. Try creating VM again

**For Windows 10/11 - Also check Hyper-V:**
1. Press **Windows + R**
2. Type: `optionalfeatures`
3. Press **Enter**
4. **UNCHECK** these if checked:
   - Hyper-V
   - Virtual Machine Platform
   - Windows Hypervisor Platform
5. Click OK, restart PC

---

### Problem 2: VM Shows Black Screen

**Cause:** Graphics settings or VT-x/AMD-V disabled

**Fix 1: Change Graphics Controller**
1. Power off VM
2. Settings → Display → Screen
3. Change **Graphics Controller** to: **VBoxVGA** (instead of VMSVGA)
4. Uncheck 3D Acceleration
5. Start VM

**Fix 2: Enable VT-x/AMD-V** (see Problem 1 above)

---

### Problem 3: VM is Very Slow

**Causes:** Not enough RAM/CPU allocated

**Fix:**
1. Power off VM
2. Settings → System
3. **Motherboard tab:** Increase RAM (4096 MB minimum)
4. **Processor tab:** Increase to 2-4 CPUs
5. Settings → Display → Increase Video Memory to 128 MB
6. Start VM

---

### Problem 4: Can't Find ISO File When Attaching

**Fix:**
1. Open File Explorer
2. Press **Windows + S**, search: `*.iso`
3. Find: `ubuntu-XX.XX-desktop-amd64.iso`
4. Note full path
5. In VirtualBox Settings → Storage → Click DVD icon
6. Choose disk file → Browse to that exact path

**If ISO was deleted:**
- Download again from: https://ubuntu.com/download/desktop
- Takes 10-15 minutes (3-4 GB file)

---

### Problem 5: "VT-x is disabled in BIOS" Error

**Fix:** See Problem 1 (enable virtualization in BIOS)

---

### Problem 6: Ubuntu Stuck at Purple Screen

**Fix:**
1. Press **Esc** key repeatedly during purple screen
2. Shows boot options
3. Select: **Ubuntu (recovery mode)**
4. Select: **Resume normal boot**

**Or:**
1. Edit boot parameters (press 'e' at GRUB menu)
2. Find line with `quiet splash`
3. Replace with: `nomodeset`
4. Press F10 to boot

---

## 🎯 Quick Reference: VM Creation Summary

**Total time:** 45-60 minutes (mostly waiting for Ubuntu to install)

**Steps:**
1. VirtualBox → New → Name: Ubuntu, Type: Linux, Version: Ubuntu 64-bit
2. RAM: 4096 MB
3. Hard disk: 25-50 GB, VDI, Dynamically allocated
4. Settings → Storage → Attach ISO to DVD drive
5. Settings → System → 2 CPUs, Enable PAE/NX
6. Settings → Display → 128 MB video memory
7. Start VM
8. Install Ubuntu (30 min)
9. Restart, login
10. Devices → Insert Guest Additions → Install
11. Restart
12. Done!

---

## 🔧 After Installation: Eject the ISO

**The D: drive DVD issue you had will be fixed:**

**Method 1: In VirtualBox (with VM running)**
1. VM window menu: **Devices** → **Optical Drives**
2. Click the ISO filename to uncheck it
3. D: drive disappears from Windows

**Method 2: In VirtualBox Manager (VM powered off)**
1. Select VM → Settings → Storage
2. Click DVD drive (shows ISO filename)
3. Click DVD icon on right → **Remove Disk from Virtual Drive**
4. Click OK

**Method 3: Just eject in Windows**
1. Right-click D: drive
2. Eject
3. (It might come back until you use Method 1 or 2)

---

## 💡 Pro Tips

1. **Take snapshots** before major changes:
   - VM powered off → Right-click VM → Snapshots → Take
   - Can restore if something breaks

2. **Enable bidirectional clipboard:**
   - Settings → General → Advanced → Shared Clipboard: Bidirectional

3. **Full screen mode:**
   - Press **Right Ctrl + F**
   - Press again to exit

4. **Pause VM instead of shutting down:**
   - VM window → Machine → Pause
   - Resumes instantly (saves time)

5. **Clone VM for experiments:**
   - Right-click VM → Clone
   - Test risky stuff on clone

---

## 📚 What to Do After Ubuntu is Installed

**Essential:**
- [ ] Install updates (Software Updater)
- [ ] Install Guest Additions
- [ ] Test internet connection (open Firefox)
- [ ] Create snapshot ("Fresh Install")

**Nice to Have:**
- [ ] Install development tools: `sudo apt install build-essential`
- [ ] Install Git: `sudo apt install git`
- [ ] Install VS Code or your preferred editor
- [ ] Set up shared folder with Windows

**For your trading project:**
- [ ] Install Python: `sudo apt install python3 python3-pip`
- [ ] Install Docker: Follow official Docker docs for Ubuntu
- [ ] Install kubectl for Kubernetes
- [ ] Clone your trading repo

---

## 🚀 You're Ready!

**Current state:** ISO file auto-mounting as D: drive

**After following this guide:**
- ✅ Full Ubuntu VM running in VirtualBox
- ✅ Can use Ubuntu alongside Windows
- ✅ ISO no longer auto-mounts (you'll eject it after install)
- ✅ Can deploy your trading system to Ubuntu VM

**Next step:** Follow the guide above to create your VM!

Let me know if you get stuck on any step!

---

*Guide created: January 17, 2026*
*For: VirtualBox 7.x + Ubuntu 22.04/24.04*
*Difficulty: Beginner-friendly*
