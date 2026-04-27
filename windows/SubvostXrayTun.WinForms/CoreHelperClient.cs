using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;
using System.Web.Script.Serialization;

namespace SubvostXrayTun.WinForms
{
    internal sealed class CoreHelperClient
    {
        private readonly JavaScriptSerializer serializer = new JavaScriptSerializer();

        public Dictionary<string, object> Run(params string[] args)
        {
            string helperPath = ResolveHelperPath();
            string arguments = BuildArguments(helperPath, args);
            string executable = ResolveExecutable(helperPath);

            ProcessStartInfo info = new ProcessStartInfo
            {
                FileName = executable,
                Arguments = arguments,
                UseShellExecute = false,
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                CreateNoWindow = true,
                StandardOutputEncoding = Encoding.UTF8,
                StandardErrorEncoding = Encoding.UTF8,
                WorkingDirectory = ResolveProjectRoot()
            };
            info.EnvironmentVariables["SUBVOST_PROJECT_ROOT"] = ResolveProjectRoot();

            using (Process process = Process.Start(info))
            {
                if (process == null)
                {
                    throw new InvalidOperationException("Не удалось запустить служебный модуль.");
                }

                string stdout = process.StandardOutput.ReadToEnd();
                string stderr = process.StandardError.ReadToEnd();
                process.WaitForExit();

                Dictionary<string, object> payload = ParsePayload(stdout);
                if (!payload.ContainsKey("ok"))
                {
                    payload["ok"] = process.ExitCode == 0;
                }
                if (process.ExitCode != 0 && !String.IsNullOrWhiteSpace(stderr))
                {
                    payload["helper_stderr"] = stderr.Trim();
                }
                return payload;
            }
        }

        private Dictionary<string, object> ParsePayload(string stdout)
        {
            if (String.IsNullOrWhiteSpace(stdout))
            {
                throw new InvalidOperationException("Служебный модуль не вернул JSON.");
            }

            object raw = serializer.DeserializeObject(stdout);
            Dictionary<string, object> payload = raw as Dictionary<string, object>;
            if (payload == null)
            {
                throw new InvalidOperationException("Служебный модуль вернул JSON неожиданного формата.");
            }
            return payload;
        }

        private static string ResolveHelperPath()
        {
            string explicitHelper = Environment.GetEnvironmentVariable("SUBVOST_CORE_HELPER");
            if (!String.IsNullOrWhiteSpace(explicitHelper) && File.Exists(explicitHelper))
            {
                return explicitHelper;
            }

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            string packagedHelper = Path.Combine(baseDir, "tools", "subvost-core.exe");
            if (File.Exists(packagedHelper))
            {
                return packagedHelper;
            }

            string flatHelper = Path.Combine(baseDir, "subvost-core.exe");
            if (File.Exists(flatHelper))
            {
                return flatHelper;
            }

            string sourceHelper = Path.Combine(ResolveProjectRoot(), "gui", "windows_core_cli.py");
            if (File.Exists(sourceHelper))
            {
                return sourceHelper;
            }

            throw new FileNotFoundException("Не найден служебный модуль `subvost-core.exe` или `gui\\windows_core_cli.py`.");
        }

        private static string ResolveExecutable(string helperPath)
        {
            if (helperPath.EndsWith(".py", StringComparison.OrdinalIgnoreCase))
            {
                string python = Environment.GetEnvironmentVariable("SUBVOST_PYTHON");
                return String.IsNullOrWhiteSpace(python) ? "python" : python;
            }
            return helperPath;
        }

        private static string BuildArguments(string helperPath, string[] args)
        {
            List<string> parts = new List<string>();
            if (helperPath.EndsWith(".py", StringComparison.OrdinalIgnoreCase))
            {
                parts.Add(Quote(helperPath));
            }
            foreach (string arg in args)
            {
                parts.Add(Quote(arg));
            }
            parts.Add("--json");
            return String.Join(" ", parts.ToArray());
        }

        private static string Quote(string value)
        {
            return "\"" + value.Replace("\"", "\\\"") + "\"";
        }

        private static string ResolveProjectRoot()
        {
            string explicitRoot = Environment.GetEnvironmentVariable("SUBVOST_PROJECT_ROOT");
            if (!String.IsNullOrWhiteSpace(explicitRoot))
            {
                return explicitRoot;
            }

            string baseDir = AppDomain.CurrentDomain.BaseDirectory;
            DirectoryInfo current = new DirectoryInfo(baseDir);
            while (current != null)
            {
                if (File.Exists(Path.Combine(current.FullName, "xray-tun-subvost.json")))
                {
                    return current.FullName;
                }
                current = current.Parent;
            }
            return baseDir;
        }

        public static string Text(IDictionary source, string key, string fallback)
        {
            if (source == null || !source.Contains(key) || source[key] == null)
            {
                return fallback;
            }
            return Convert.ToString(source[key]);
        }

        public static IDictionary Dict(IDictionary source, string key)
        {
            if (source == null || !source.Contains(key))
            {
                return new Dictionary<string, object>();
            }
            IDictionary dict = source[key] as IDictionary;
            return dict ?? new Dictionary<string, object>();
        }

        public static IList List(IDictionary source, string key)
        {
            if (source == null || !source.Contains(key))
            {
                return new object[0];
            }
            IList list = source[key] as IList;
            return list ?? new object[0];
        }

        public static bool Ok(IDictionary payload)
        {
            if (payload == null || !payload.Contains("ok") || payload["ok"] == null)
            {
                return false;
            }
            return Convert.ToBoolean(payload["ok"]);
        }
    }
}
