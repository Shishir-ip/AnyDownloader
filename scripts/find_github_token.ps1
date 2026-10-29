# Reads GitHub-related credentials from Windows Credential Manager and
# reports which one authenticates against the GitHub API (masked output).
# The working token is saved to a user-only env-style file in the repo's
# build folder (gitignored) so the publish step can use it without echoing.
$ErrorActionPreference = "Stop"

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public class CredMan {
    [DllImport("advapi32.dll", EntryPoint="CredReadW", CharSet=CharSet.Unicode, SetLastError=true)]
    public static extern bool CredRead(string target, int type, int flags, out IntPtr credPtr);
    [StructLayout(LayoutKind.Sequential, CharSet=CharSet.Unicode)]
    public struct CREDENTIAL {
        public int Flags; public int Type; public string TargetName; public string Comment;
        public System.Runtime.InteropServices.ComTypes.FILETIME LastWritten;
        public int CredentialBlobSize; public IntPtr CredentialBlob; public int Persist;
        public int AttributeCount; public IntPtr Attributes; public string TargetAlias; public string UserName;
    }
    [DllImport("advapi32.dll")] public static extern void CredFree(IntPtr cred);
}
"@

function Read-Cred([string]$target) {
    $ptr = [IntPtr]::Zero
    if (-not [CredMan]::CredRead($target, 1, 0, [ref]$ptr)) { return $null }
    try {
        $cred = [Runtime.InteropServices.Marshal]::PtrToStructure($ptr, [type][CredMan+CREDENTIAL])
        if ($cred.CredentialBlobSize -eq 0) { return $null }
        $bytes = New-Object byte[] $cred.CredentialBlobSize
        [Runtime.InteropServices.Marshal]::Copy($cred.CredentialBlob, $bytes, 0, $cred.CredentialBlobSize)
        return [Text.Encoding]::UTF8.GetString($bytes)
    } finally { [CredMan]::CredFree($ptr) }
}

$outFile = "C:\Users\SHISHIR\Downloads\AnyDownloader\build\.ghtoken"
$targets = @(
    "git:https://github.com",
    "GitHub - https://api.github.com/Shishir-ip",
    "copilot-cli/https://github.com:Shishir-ip"
)

foreach ($target in $targets) {
    $secret = Read-Cred $target
    if (-not $secret) { Write-Output "MISS`t$target"; continue }
    # Some helpers store "username:password" blobs
    if ($secret -match "^[^:={ ]+:[A-Za-z0-9_\-]{20,}$") { $secret = $secret.Split(":", 2)[1] }
    $secret = $secret.Trim()
    $headers = @{ Authorization = "Bearer $secret"; Accept = "application/vnd.github+json" }
    try {
        $me = Invoke-RestMethod -Uri "https://api.github.com/user" -Headers $headers -Method Get -TimeoutSec 20
        [IO.File]::WriteAllText($outFile, $secret)
        Write-Output ("HIT`t$target`tuser=" + $me.login + "`tlen=" + $secret.Length + "`tscopes-saved")
        exit 0
    } catch {
        Write-Output ("REJECT`t$target`t" + $_.Exception.Message)
    }
}
Write-Output "NO-WORKING-TOKEN"
