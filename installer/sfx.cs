// Zelf-uitpakkende stub voor "De Vierkante Paal".
// Wordt door installer\bouw-installer.ps1 gecompileerd met de C#-compiler
// van .NET Framework 4 (csc.exe, aanwezig op elke Windows 10/11).
// Het pakket (dvp-pakket.zip), de wizard (installeer.ps1) en het logo
// zitten als resources ingebed; deze stub pakt ze uit naar een tijdelijke
// map en start de wizard.

using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

static class DvpSetup
{
    static readonly string[] Bestanden =
    {
        "dvp-pakket.zip",
        "installeer.ps1",
        "logo.png"
    };

    [STAThread]
    static int Main()
    {
        string tmp = Path.Combine(
            Path.GetTempPath(),
            "DVP_setup_" + Guid.NewGuid().ToString("N").Substring(0, 8));
        Directory.CreateDirectory(tmp);

        Assembly asm = Assembly.GetExecutingAssembly();
        try
        {
            foreach (string naam in Bestanden)
            {
                using (Stream bron = asm.GetManifestResourceStream("res." + naam))
                using (FileStream doel = File.Create(Path.Combine(tmp, naam)))
                {
                    if (bron == null)
                        throw new Exception("ontbrekende resource: " + naam);
                    bron.CopyTo(doel);
                }
            }
        }
        catch (Exception ex)
        {
            MessageBox.Show("Het uitpakken is mislukt:\n\n" + ex.Message,
                "De Vierkante Paal", MessageBoxButtons.OK, MessageBoxIcon.Error);
            OpruimenStil(tmp);
            return 1;
        }

        int code = 1;
        try
        {
            ProcessStartInfo psi = new ProcessStartInfo();
            psi.FileName = "powershell.exe";
            psi.Arguments = "-NoProfile -ExecutionPolicy Bypass -File \""
                + Path.Combine(tmp, "installeer.ps1") + "\"";
            psi.UseShellExecute = false;
            psi.WorkingDirectory = tmp;

            Process p = Process.Start(psi);
            p.WaitForExit();
            code = p.ExitCode;
        }
        catch (Exception ex)
        {
            MessageBox.Show("Kon de installatie niet starten:\n\n" + ex.Message,
                "De Vierkante Paal", MessageBoxButtons.OK, MessageBoxIcon.Error);
        }

        OpruimenStil(tmp);
        return code;
    }

    static void OpruimenStil(string map)
    {
        try { Directory.Delete(map, true); }
        catch { /* laat Windows het later opruimen */ }
    }
}
