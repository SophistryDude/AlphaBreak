# Ubuntu Mounted as DVD Drive - Quick Fix Guide

Your D: drive is showing Ubuntu as a virtual DVD - here's what happened and how to fix it.

---

## 🔍 What Happened

**Likely Scenarios:**

### 1. VirtualBox Guest Additions (Most Common)
- You installed VirtualBox to create the Ubuntu VM
- VirtualBox mounted "Guest Additions" ISO as a virtual DVD
- This ISO appears as drive D: in Windows

### 2. Ubuntu ISO Still Mounted
- The Ubuntu installation ISO (.iso file) is mounted
- Windows treats .iso files as virtual DVD drives
- Shows up as a drive letter

### 3. Hyper-V or VMware
- Similar virtualization software auto-mounted something

---

## 🛠️ Quick Fixes

### Fix 1: Eject the Virtual DVD (Easiest - 10 seconds)

**Steps:**
1. Open **File Explorer** (Windows + E)
2. Look at **This PC** section
3. Find the D: drive labeled "Ubuntu" or "VirtualBox Guest Additions"
4. **Right-click** on it
5. Select **Eject**

**Result**: Drive disappears immediately

**Permanent?** No - might come back if VirtualBox/VM restarts

---

### Fix 2: Unmount in VirtualBox (If using VirtualBox)

**Steps:**
1. Open **VirtualBox Manager**
2. Select your Ubuntu VM (don't start it)
3. Click **Settings** (gear icon)
4. Go to **Storage** tab
5. Look under "Controller: IDE" or "Controller: SATA"
6. Find the DVD icon with "VBoxGuestAdditions.iso" or "ubuntu-XX.XX.iso"
7. Click on it
8. On the right side, click the **DVD icon**
9. Select **Remove Disk from Virtual Drive**
10. Click **OK**

**Result**: DVD won't mount on next Windows boot

**Permanent?** Yes, until you mount something else

---

### Fix 3: Disable Auto-Mount in VirtualBox (Permanent Solution)

**If you want VirtualBox to NEVER auto-mount ISOs:**

**Steps:**
1. Open **VirtualBox Manager**
2. Go to **File** → **Preferences** (Ctrl+G)
3. Click **Extensions** or **General** tab
4. Uncheck **"Mount Guest Additions automatically"** (if present)
5. Click **OK**

**Alternative via VM Settings:**
1. Select VM → **Settings**
2. **Storage** tab
3. Remove ALL optical drives you don't need
4. Click **OK**

---

### Fix 4: Change Drive Letter (If You Need D: for Something Else)

**Steps:**
1. Press **Windows + X**
2. Select **Disk Management**
3. Find the DVD drive showing Ubuntu
4. Right-click → **Change Drive Letter and Paths**
5. Click **Change**
6. Select a different letter (like Z:)
7. Click **OK**

**Result**: Ubuntu ISO moves to Z: instead of D:

**Note**: This doesn't remove it, just moves it out of the way

---

### Fix 5: Delete the ISO File (If You're Done Installing Ubuntu)

**Only if you don't need the Ubuntu installer anymore:**

**Steps:**
1. Open **File Explorer**
2. Navigate to where you downloaded Ubuntu ISO
   - Likely: `C:\Users\nicho\Downloads\`
   - Or: `C:\Users\nicho\VirtualBox VMs\`
3. Find file like: `ubuntu-22.04.3-desktop-amd64.iso`
4. Right-click → **Delete** (or Shift+Delete to skip Recycle Bin)

**Result**: ISO is gone, but might still be mounted until you eject

**Warning**: Only delete if you don't plan to reinstall Ubuntu

---

## 🔍 Diagnostic: Figure Out What's Mounted

### Check What ISO is Mounted

**Option 1: File Explorer**
1. Open **File Explorer**
2. Right-click on D: drive (Ubuntu DVD)
3. Select **Properties**
4. Look at **Location** field - shows path to .iso file

**Option 2: Disk Management**
1. Press **Windows + X** → **Disk Management**
2. Find the DVD drive
3. Shows type (Virtual DVD, CD-ROM, etc.)

**Option 3: Command Prompt**
```cmd
wmic logicaldisk get caption,volumename,description
```
Shows all drives and their types

---

## 🎯 Recommended Action (Based on Your Situation)

### If You Just Installed Ubuntu VM for the First Time:
✅ **Do Fix #1** (Eject) - Quick and harmless
✅ **Then do Fix #2** (Unmount in VirtualBox) - Prevents it coming back

### If You're Done Installing Ubuntu and Don't Need ISO:
✅ **Do Fix #1** (Eject)
✅ **Then do Fix #5** (Delete ISO file) - Frees up ~4GB of space

### If You Want to Keep Using the VM but Hate the DVD:
✅ **Do Fix #2** (Unmount in VirtualBox)
✅ **Optional: Fix #3** (Disable auto-mount)

---

## ❓ FAQ

### Q: Will ejecting harm my Ubuntu VM?
**A:** No. The VM is stored separately as a virtual hard disk (.vdi file). The ISO is just the installer.

### Q: Do I need Guest Additions?
**A:** Only if you want:
- Shared clipboard (copy/paste between Windows and Ubuntu)
- Shared folders
- Better screen resolution
- Drag-and-drop files

If you don't use these features, you can eject it.

### Q: Can I reinstall Ubuntu without the ISO?
**A:** No, you'll need to download it again from ubuntu.com. If unsure, keep the ISO.

### Q: Why is it taking my D: drive letter?
**A:** Windows assigns letters alphabetically. C: is your main drive, D: was next available. You can change it with Fix #4.

### Q: Will this happen every time I start Windows?
**A:** If VirtualBox is set to auto-mount Guest Additions, yes. Use Fix #2 or #3 to stop it.

---

## 🛠️ Step-by-Step: Full Cleanup (If You Want It Gone)

**Total Time: 2 minutes**

### Step 1: Eject the Drive
1. Open File Explorer (Windows + E)
2. Right-click D: drive (Ubuntu)
3. Click **Eject**

### Step 2: Unmount in VirtualBox
1. Open VirtualBox
2. Select Ubuntu VM
3. Click **Settings** → **Storage**
4. Select the ISO under IDE/SATA Controller
5. Click DVD icon → **Remove Disk from Virtual Drive**
6. Click **OK**

### Step 3: (Optional) Delete ISO
1. Go to Downloads folder
2. Find `ubuntu-*.iso` (probably 3-4 GB)
3. Delete it

**Done!** DVD won't come back.

---

## 🔧 If Nothing Works (Nuclear Option)

### Disable VirtualBox Extensions Service

**Steps:**
1. Press **Windows + R**
2. Type: `services.msc`
3. Press **Enter**
4. Scroll to **VirtualBox Guest Additions Service** (if exists)
5. Right-click → **Properties**
6. Set **Startup type** to **Disabled**
7. Click **Stop** (if running)
8. Click **OK**
9. Restart computer

**Warning**: This might break some VirtualBox features

---

## 💡 Pro Tip: Prevent Future Auto-Mounts

**Windows 10/11 Setting:**
1. Open **Settings** (Windows + I)
2. Go to **Devices** → **AutoPlay**
3. Find **CD/DVD** dropdown
4. Set to **Take no action**

**Result**: Windows won't auto-open DVDs anymore

---

## ✅ Quick Checklist

**To Remove the DVD Right Now:**
- [ ] Open File Explorer
- [ ] Right-click D: drive (Ubuntu)
- [ ] Click Eject
- [ ] Done (30 seconds)

**To Prevent It Coming Back:**
- [ ] Open VirtualBox
- [ ] Select Ubuntu VM → Settings → Storage
- [ ] Remove ISO from Controller
- [ ] Click OK
- [ ] Done (2 minutes)

**To Free Up Space:**
- [ ] Delete ubuntu-*.iso from Downloads
- [ ] Empty Recycle Bin
- [ ] Gain ~4GB (1 minute)

---

## 🎯 One-Command Fix (PowerShell)

If you just want it gone NOW:

**Open PowerShell as Administrator:**
```powershell
# Eject D: drive
(New-Object -ComObject Shell.Application).NameSpace(17).ParseName("D:").InvokeVerb("Eject")
```

**Explanation**: Tells Windows to eject the D: drive

**Result**: DVD disappears instantly

---

## 🚀 Summary

**Your issue**: VirtualBox or Windows mounted Ubuntu ISO as virtual DVD on D: drive

**Quickest fix**:
1. Right-click D: drive → Eject (10 seconds)
2. Open VirtualBox → Settings → Storage → Remove ISO (2 minutes)

**That's it!** The "DVD" is harmless but annoying. Ejecting it won't break anything.

Let me know if you want me to walk through any specific fix!

---

*Guide created: January 17, 2026*
*For: Windows 10/11 with VirtualBox*
