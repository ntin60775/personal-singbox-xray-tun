using System;
using System.Collections;
using System.Collections.Generic;
using System.Drawing;
using System.Threading.Tasks;
using System.Windows.Forms;

namespace SubvostXrayTun.WinForms
{
    internal sealed class MainForm : Form
    {
        private readonly CoreHelperClient helper;
        private readonly Label statusLabel = new Label();
        private readonly Label detailLabel = new Label();
        private readonly Label activeNodeLabel = new Label();
        private readonly ListView nodesList = new ListView();
        private readonly TextBox subscriptionNameBox = new TextBox();
        private readonly TextBox subscriptionUrlBox = new TextBox();
        private readonly TextBox logBox = new TextBox();
        private readonly Button refreshButton = new Button();
        private readonly Button connectButton = new Button();
        private readonly Button disconnectButton = new Button();
        private readonly Button diagnosticsButton = new Button();
        private readonly Button addSubscriptionButton = new Button();
        private readonly Button activateNodeButton = new Button();

        public MainForm(CoreHelperClient helper)
        {
            this.helper = helper;
            Text = "Subvost Xray Tun";
            StartPosition = FormStartPosition.CenterScreen;
            MinimumSize = new Size(900, 620);
            Size = new Size(980, 680);
            Font = new Font("Segoe UI", 9F);
            BuildLayout();
            Shown += async (sender, args) => await RefreshStatusAsync();
        }

        private void BuildLayout()
        {
            TableLayoutPanel root = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 1,
                RowCount = 5,
                Padding = new Padding(12)
            };
            root.RowStyles.Add(new RowStyle(SizeType.Absolute, 86));
            root.RowStyles.Add(new RowStyle(SizeType.Absolute, 44));
            root.RowStyles.Add(new RowStyle(SizeType.Percent, 100));
            root.RowStyles.Add(new RowStyle(SizeType.Absolute, 96));
            root.RowStyles.Add(new RowStyle(SizeType.Absolute, 120));
            Controls.Add(root);

            Panel statusPanel = new Panel { Dock = DockStyle.Fill };
            statusLabel.AutoSize = false;
            statusLabel.Font = new Font(Font.FontFamily, 16F, FontStyle.Bold);
            statusLabel.Text = "Загрузка статуса";
            statusLabel.Dock = DockStyle.Top;
            statusLabel.Height = 34;
            detailLabel.AutoSize = false;
            detailLabel.Text = "Служебный модуль ещё не ответил.";
            detailLabel.Dock = DockStyle.Top;
            detailLabel.Height = 24;
            activeNodeLabel.AutoSize = false;
            activeNodeLabel.Text = "Активный узел: —";
            activeNodeLabel.Dock = DockStyle.Top;
            activeNodeLabel.Height = 24;
            statusPanel.Controls.Add(activeNodeLabel);
            statusPanel.Controls.Add(detailLabel);
            statusPanel.Controls.Add(statusLabel);
            root.Controls.Add(statusPanel, 0, 0);

            FlowLayoutPanel actionsPanel = new FlowLayoutPanel { Dock = DockStyle.Fill, FlowDirection = FlowDirection.LeftToRight };
            ConfigureButton(refreshButton, "Обновить", async () => await RefreshStatusAsync());
            ConfigureButton(connectButton, "Подключиться", async () => await RunHelperActionAsync("runtime", "start"));
            ConfigureButton(disconnectButton, "Отключиться", async () => await RunHelperActionAsync("runtime", "stop"));
            ConfigureButton(diagnosticsButton, "Диагностика", async () => await RunHelperActionAsync("diagnostics", "capture"));
            ConfigureButton(activateNodeButton, "Выбрать узел", async () => await ActivateSelectedNodeAsync());
            actionsPanel.Controls.Add(refreshButton);
            actionsPanel.Controls.Add(connectButton);
            actionsPanel.Controls.Add(disconnectButton);
            actionsPanel.Controls.Add(diagnosticsButton);
            actionsPanel.Controls.Add(activateNodeButton);
            root.Controls.Add(actionsPanel, 0, 1);

            nodesList.Dock = DockStyle.Fill;
            nodesList.View = View.Details;
            nodesList.FullRowSelect = true;
            nodesList.MultiSelect = false;
            nodesList.HideSelection = false;
            nodesList.Columns.Add("Узел", 280);
            nodesList.Columns.Add("Профиль", 180);
            nodesList.Columns.Add("Протокол", 90);
            nodesList.Columns.Add("Адрес", 220);
            nodesList.Columns.Add("Состояние", 130);
            root.Controls.Add(nodesList, 0, 2);

            TableLayoutPanel subscriptionPanel = new TableLayoutPanel
            {
                Dock = DockStyle.Fill,
                ColumnCount = 3,
                RowCount = 2,
                Padding = new Padding(0, 8, 0, 8)
            };
            subscriptionPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 210));
            subscriptionPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Percent, 100));
            subscriptionPanel.ColumnStyles.Add(new ColumnStyle(SizeType.Absolute, 150));
            subscriptionPanel.RowStyles.Add(new RowStyle(SizeType.Absolute, 28));
            subscriptionPanel.RowStyles.Add(new RowStyle(SizeType.Absolute, 36));
            subscriptionPanel.Controls.Add(new Label { Text = "Название", Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft }, 0, 0);
            subscriptionPanel.Controls.Add(new Label { Text = "Ссылка подписки", Dock = DockStyle.Fill, TextAlign = ContentAlignment.MiddleLeft }, 1, 0);
            subscriptionPanel.Controls.Add(subscriptionNameBox, 0, 1);
            subscriptionPanel.Controls.Add(subscriptionUrlBox, 1, 1);
            ConfigureButton(addSubscriptionButton, "Добавить", async () => await AddSubscriptionAsync());
            subscriptionPanel.Controls.Add(addSubscriptionButton, 2, 1);
            root.Controls.Add(subscriptionPanel, 0, 3);

            logBox.Dock = DockStyle.Fill;
            logBox.Multiline = true;
            logBox.ReadOnly = true;
            logBox.ScrollBars = ScrollBars.Vertical;
            logBox.BackColor = Color.White;
            root.Controls.Add(logBox, 0, 4);
        }

        private void ConfigureButton(Button button, string text, Func<Task> action)
        {
            button.Text = text;
            button.AutoSize = false;
            button.Width = 132;
            button.Height = 32;
            button.Margin = new Padding(0, 4, 8, 4);
            button.Click += async (sender, args) => await action();
        }

        private async Task RefreshStatusAsync()
        {
            await RunAndApplyAsync("status");
        }

        private async Task RunHelperActionAsync(params string[] args)
        {
            await RunAndApplyAsync(args);
        }

        private async Task AddSubscriptionAsync()
        {
            string url = subscriptionUrlBox.Text.Trim();
            if (String.IsNullOrWhiteSpace(url))
            {
                AppendLog("Ссылка подписки не заполнена.");
                return;
            }
            await RunAndApplyAsync("subscriptions", "add", "--name", subscriptionNameBox.Text.Trim(), "--url", url);
        }

        private async Task ActivateSelectedNodeAsync()
        {
            if (nodesList.SelectedItems.Count == 0)
            {
                AppendLog("Сначала выбери узел в списке.");
                return;
            }
            ListViewItem item = nodesList.SelectedItems[0];
            string[] ids = Convert.ToString(item.Tag).Split('\t');
            if (ids.Length != 2)
            {
                AppendLog("Не удалось определить выбранный узел.");
                return;
            }
            string profileId = ids[0];
            string nodeId = ids[1];
            await RunAndApplyAsync("nodes", "activate", "--profile-id", profileId, "--node-id", nodeId);
        }

        private async Task RunAndApplyAsync(params string[] args)
        {
            SetBusy(true);
            try
            {
                Dictionary<string, object> payload = await Task.Run(() => helper.Run(args));
                ApplyPayload(payload);
            }
            catch (Exception exc)
            {
                AppendLog("Ошибка служебного модуля: " + exc.Message);
                statusLabel.Text = "Ошибка";
                detailLabel.Text = exc.Message;
            }
            finally
            {
                SetBusy(false);
            }
        }

        private void SetBusy(bool busy)
        {
            refreshButton.Enabled = !busy;
            connectButton.Enabled = !busy;
            disconnectButton.Enabled = !busy;
            diagnosticsButton.Enabled = !busy;
            addSubscriptionButton.Enabled = !busy;
            activateNodeButton.Enabled = !busy;
            Cursor = busy ? Cursors.WaitCursor : Cursors.Default;
        }

        private void ApplyPayload(Dictionary<string, object> payload)
        {
            IDictionary status = CoreHelperClient.Dict(payload, "status");
            IDictionary summary = CoreHelperClient.Dict(status, "summary");
            IDictionary connection = CoreHelperClient.Dict(status, "connection");
            IDictionary data = CoreHelperClient.Dict(payload, "data");

            statusLabel.Text = CoreHelperClient.Text(summary, "label", CoreHelperClient.Text(payload, "message", "Статус получен."));
            detailLabel.Text = CoreHelperClient.Text(summary, "description", CoreHelperClient.Text(payload, "message", ""));
            activeNodeLabel.Text = "Активный узел: " + CoreHelperClient.Text(connection, "active_name", "—");
            AppendLog(CoreHelperClient.Text(payload, "message", "Служебный модуль ответил."));

            IList nodes = CoreHelperClient.List(data, "nodes");
            if (nodes.Count > 0)
            {
                RenderNodes(nodes);
            }

            if (!CoreHelperClient.Ok(payload))
            {
                IDictionary error = CoreHelperClient.Dict(payload, "error");
                string message = CoreHelperClient.Text(error, "message", CoreHelperClient.Text(payload, "message", "Действие завершилось ошибкой."));
                AppendLog("Ошибка: " + message);
            }
        }

        private void RenderNodes(IList nodes)
        {
            nodesList.BeginUpdate();
            nodesList.Items.Clear();
            foreach (object raw in nodes)
            {
                IDictionary node = raw as IDictionary;
                if (node == null)
                {
                    continue;
                }
                string name = CoreHelperClient.Text(node, "name", "Без имени");
                string profile = CoreHelperClient.Text(node, "profile_name", "Без профиля");
                string protocol = CoreHelperClient.Text(node, "protocol", "—");
                string endpoint = CoreHelperClient.Text(node, "endpoint", "—");
                string state = CoreHelperClient.Text(node, "active", "False") == "True" ? "Активный" : "Доступен";
                ListViewItem item = new ListViewItem(name);
                item.Tag = CoreHelperClient.Text(node, "profile_id", "") + "\t" + CoreHelperClient.Text(node, "node_id", "");
                item.SubItems.Add(profile);
                item.SubItems.Add(protocol);
                item.SubItems.Add(endpoint);
                item.SubItems.Add(state);
                nodesList.Items.Add(item);
            }
            nodesList.EndUpdate();
        }

        private void AppendLog(string message)
        {
            logBox.AppendText(DateTime.Now.ToString("HH:mm:ss") + "  " + message + Environment.NewLine);
        }
    }
}
