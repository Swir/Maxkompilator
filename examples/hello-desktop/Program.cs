using System;
using System.Drawing;
using System.IO;
using System.Windows.Forms;

internal static class Program
{
    [STAThread]
    static int Main()
    {
        ApplicationConfiguration.Initialize();
        string resource = File.ReadAllText(Path.Combine(AppContext.BaseDirectory, "Assets", "greeting.txt")).Trim();
        if (resource != "MAXKOMPILATOR_DESKTOP_RESOURCE_OK") return 10;
        using var window = new Form { Text = "Maxkompilator .NET desktop test", ClientSize = new Size(560, 140) };
        using var label = new Label { Text = resource, Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleCenter };
        window.Controls.Add(label);
        bool painted = false, qualified = false;
        window.Paint += (_, _) => painted = true;
        using var timer = new System.Windows.Forms.Timer { Interval = 1000 };
        window.Shown += (_, _) => timer.Start();
        timer.Tick += (_, _) =>
        {
            timer.Stop();
            qualified = painted && window.IsHandleCreated && window.Visible && label.Visible && label.Text == resource;
            if (qualified) Console.WriteLine("MAXKOMPILATOR_DESKTOP_RUNTIME_OK");
            window.Close();
        };
        Application.Run(window);
        return qualified ? 0 : 11;
    }
}
