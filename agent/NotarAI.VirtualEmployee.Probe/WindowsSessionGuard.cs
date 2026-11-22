using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;

namespace NotarAI.VirtualEmployee.Probe;

/// <summary>
/// Fail-closed Windows desktop check for synthetic GUI automation.
/// A non-Session-0 user process is NOT sufficient: disconnected RDP and
/// Winlogon lock desktops must also block work. Returns only a boolean;
/// never logs session users, window titles or desktop content.
/// </summary>
internal static class WindowsSessionGuard
{
    private const int WtsConnectState = 8; // WTS_INFO_CLASS.WTSConnectState
    private const int WtsActive = 0;       // WTS_CONNECTSTATE_CLASS.WTSActive
    private const int UoiName = 2;         // UOI_NAME
    private const uint DesktopReadObjects = 0x0001;

    [DllImport("wtsapi32.dll", EntryPoint = "WTSQuerySessionInformationW", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool WtsQuerySessionInformation(
        IntPtr server, int sessionId, int infoClass, out IntPtr buffer, out int bytes);

    [DllImport("wtsapi32.dll", SetLastError = false)]
    private static extern void WTSFreeMemory(IntPtr buffer);

    [DllImport("user32.dll", SetLastError = true)]
    private static extern IntPtr OpenInputDesktop(uint flags,
        [MarshalAs(UnmanagedType.Bool)] bool inherit, uint desiredAccess);

    [DllImport("user32.dll", EntryPoint = "GetUserObjectInformationW", CharSet = CharSet.Unicode,
        SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool GetUserObjectInformation(
        IntPtr handle, int index, StringBuilder info, int length, out int lengthNeeded);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool CloseDesktop(IntPtr handle);

    public static bool IsReady()
    {
        if (!OperatingSystem.IsWindows() || !Environment.UserInteractive)
            return false;

        try
        {
            using var process = Process.GetCurrentProcess();
            var sessionId = process.SessionId;
            if (sessionId <= 0)
                return false;

            if (!WtsQuerySessionInformation(IntPtr.Zero, sessionId, WtsConnectState,
                    out var buffer, out var bytes))
                return false;
            if (buffer == IntPtr.Zero)
                return false;
            var active = false;
            try
            {
                active = bytes >= sizeof(int) && Marshal.ReadInt32(buffer) == WtsActive;
            }
            finally
            {
                WTSFreeMemory(buffer);
            }
            if (!active)
                return false;

            // On a locked workstation the input desktop is generally
            // Winlogon (or cannot be opened). We require the user 'Default'
            // desktop and fail closed on access-denied / unexpected desktop.
            var desktop = OpenInputDesktop(0, false, DesktopReadObjects);
            if (desktop == IntPtr.Zero)
                return false;
            try
            {
                var name = new StringBuilder(128);
                if (!GetUserObjectInformation(desktop, UoiName, name, name.Capacity * 2,
                        out var requiredBytes))
                    return false;
                return requiredBytes > 0 &&
                       string.Equals(name.ToString(), "Default", StringComparison.OrdinalIgnoreCase);
            }
            finally
            {
                CloseDesktop(desktop);
            }
        }
        catch (Exception ex) when (ex is DllNotFoundException or EntryPointNotFoundException or
                                   InvalidOperationException or System.ComponentModel.Win32Exception)
        {
            return false;
        }
    }
}
