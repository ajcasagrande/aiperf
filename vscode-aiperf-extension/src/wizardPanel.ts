// SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import * as vscode from 'vscode';

/**
 * Plugin Wizard Webview Panel
 *
 * Provides UI wizard for creating AIPerf plugins following AIP-001 specification
 */
export class PluginWizardPanel {
    public static currentPanel: PluginWizardPanel | undefined;
    private readonly _panel: vscode.WebviewPanel;
    private readonly _extensionUri: vscode.Uri;
    private _disposables: vscode.Disposable[] = [];

    public static createOrShow(extensionUri: vscode.Uri) {
        const column = vscode.window.activeTextEditor
            ? vscode.window.activeTextEditor.viewColumn
            : undefined;

        if (PluginWizardPanel.currentPanel) {
            PluginWizardPanel.currentPanel._panel.reveal(column);
            return;
        }

        const panel = vscode.window.createWebviewPanel(
            'aiperfPluginWizard',
            'AIPerf Plugin Wizard (AIP-001)',
            column || vscode.ViewColumn.One,
            {
                enableScripts: true,
                retainContextWhenHidden: true,
                localResourceRoots: [
                    vscode.Uri.joinPath(extensionUri, 'media')
                ]
            }
        );

        PluginWizardPanel.currentPanel = new PluginWizardPanel(panel, extensionUri);
    }

    private constructor(panel: vscode.WebviewPanel, extensionUri: vscode.Uri) {
        this._panel = panel;
        this._extensionUri = extensionUri;

        this._panel.webview.html = this._getHtmlForWebview(this._panel.webview);

        this._panel.onDidDispose(() => this.dispose(), null, this._disposables);

        this._panel.webview.onDidReceiveMessage(
            message => this._handleMessage(message),
            null,
            this._disposables
        );
    }

    private async _handleMessage(message: any) {
        switch (message.command) {
            case 'createPlugin':
                await this._createPlugin(message.data);
                return;
            case 'validateName':
                this._validatePluginName(message.data);
                return;
        }
    }

    private async _createPlugin(pluginConfig: any) {
        // Call Python plugin wizard with configuration
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            vscode.window.showErrorMessage('No workspace folder found');
            return;
        }

        // Execute plugin wizard Python script
        const pythonPath = vscode.workspace.getConfiguration('aiperf').get('pythonPath', 'python');
        const wizardPath = vscode.Uri.joinPath(workspaceFolder.uri, 'tools', 'plugin_wizard.py').fsPath;

        // Create config JSON for non-interactive mode
        const configJson = JSON.stringify(pluginConfig);

        const terminal = vscode.window.createTerminal({
            name: 'AIPerf Plugin Wizard',
            cwd: workspaceFolder.uri.fsPath
        });

        terminal.show();
        terminal.sendText(`${pythonPath} ${wizardPath} --config '${configJson}'`);

        vscode.window.showInformationMessage(
            'Plugin creation started in terminal. Follow the prompts to complete.'
        );

        this._panel.dispose();
    }

    private _validatePluginName(name: string) {
        // Validate plugin name is valid Python identifier
        const isValid = /^[a-z][a-z0-9_]*$/.test(name);

        this._panel.webview.postMessage({
            command: 'validationResult',
            valid: isValid,
            message: isValid ? 'Valid plugin name' : 'Must be lowercase with underscores only'
        });
    }

    private _getHtmlForWebview(webview: vscode.Webview): string {
        const styleUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'media', 'wizard.css')
        );
        const scriptUri = webview.asWebviewUri(
            vscode.Uri.joinPath(this._extensionUri, 'media', 'wizard.js')
        );

        return `<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <meta http-equiv="Content-Security-Policy"
                  content="default-src 'none'; style-src ${webview.cspSource} 'unsafe-inline'; script-src ${webview.cspSource};">
            <link href="${styleUri}" rel="stylesheet">
            <title>AIPerf Plugin Wizard</title>
        </head>
        <body>
            <div class="wizard-container">
                <header>
                    <h1>🔧 AIPerf Plugin Wizard</h1>
                    <p class="subtitle">Create plugins following AIP-001 specification</p>
                </header>

                <div class="progress-bar">
                    <div class="progress-step active" data-step="1">1. Type</div>
                    <div class="progress-step" data-step="2">2. Details</div>
                    <div class="progress-step" data-step="3">3. Config</div>
                    <div class="progress-step" data-step="4">4. Review</div>
                </div>

                <form id="pluginForm">
                    <!-- Step 1: Plugin Type -->
                    <div class="wizard-step active" data-step="1">
                        <h2>Select Plugin Type</h2>
                        <p>Choose the type of plugin you want to create (AIP-001):</p>

                        <div class="plugin-types">
                            <label class="plugin-type-card">
                                <input type="radio" name="pluginType" value="metric" required>
                                <div class="card-content">
                                    <div class="card-icon">📊</div>
                                    <h3>Metric</h3>
                                    <p>Performance metrics (TTFT, throughput, custom calculations)</p>
                                    <span class="entry-point">aiperf.metric</span>
                                </div>
                            </label>

                            <label class="plugin-type-card">
                                <input type="radio" name="pluginType" value="endpoint">
                                <div class="card-content">
                                    <div class="card-icon">🌐</div>
                                    <h3>Endpoint</h3>
                                    <p>API format handlers (Custom APIs, proprietary formats)</p>
                                    <span class="entry-point">aiperf.endpoint</span>
                                </div>
                            </label>

                            <label class="plugin-type-card">
                                <input type="radio" name="pluginType" value="data_exporter">
                                <div class="card-content">
                                    <div class="card-icon">📤</div>
                                    <h3>Data Exporter</h3>
                                    <p>Export formats (Parquet, Excel, Database)</p>
                                    <span class="entry-point">aiperf.data_exporter</span>
                                </div>
                            </label>

                            <label class="plugin-type-card">
                                <input type="radio" name="pluginType" value="transport">
                                <div class="card-content">
                                    <div class="card-icon">🔌</div>
                                    <h3>Transport</h3>
                                    <p>Communication protocols (gRPC, WebSocket)</p>
                                    <span class="entry-point">aiperf.transport</span>
                                </div>
                            </label>

                            <label class="plugin-type-card">
                                <input type="radio" name="pluginType" value="processor">
                                <div class="card-content">
                                    <div class="card-icon">⚙️</div>
                                    <h3>Processor</h3>
                                    <p>Data processors (Custom transformations)</p>
                                    <span class="entry-point">aiperf.processor</span>
                                </div>
                            </label>

                            <label class="plugin-type-card">
                                <input type="radio" name="pluginType" value="collector">
                                <div class="card-content">
                                    <div class="card-icon">📡</div>
                                    <h3>Collector</h3>
                                    <p>Data collection (Prometheus, OpenTelemetry)</p>
                                    <span class="entry-point">aiperf.collector</span>
                                </div>
                            </label>
                        </div>
                    </div>

                    <!-- Step 2: Basic Details -->
                    <div class="wizard-step" data-step="2">
                        <h2>Plugin Details</h2>

                        <div class="form-group">
                            <label for="pluginName">Plugin Name (snake_case)</label>
                            <input type="text" id="pluginName" name="pluginName"
                                   pattern="[a-z][a-z0-9_]*" required
                                   placeholder="my_custom_metric">
                            <small>Must be valid Python identifier (lowercase, underscores)</small>
                        </div>

                        <div class="form-group">
                            <label for="displayName">Display Name</label>
                            <input type="text" id="displayName" name="displayName" required
                                   placeholder="My Custom Metric">
                        </div>

                        <div class="form-group">
                            <label for="description">Description</label>
                            <textarea id="description" name="description" rows="3" required
                                      placeholder="Brief description of what this plugin does"></textarea>
                        </div>

                        <div class="form-group">
                            <label for="packageName">Package Name (PyPI)</label>
                            <input type="text" id="packageName" name="packageName" required
                                   placeholder="aiperf-my-custom-metric">
                            <small>Will be used for PyPI distribution</small>
                        </div>
                    </div>

                    <!-- Step 3: Plugin-Specific Configuration -->
                    <div class="wizard-step" data-step="3">
                        <h2 id="configTitle">Plugin Configuration</h2>

                        <!-- Metric-specific config -->
                        <div id="metricConfig" class="plugin-specific-config" style="display:none;">
                            <div class="form-group">
                                <label>Metric Type</label>
                                <select name="metricType">
                                    <option value="record">Record - Per-request calculations</option>
                                    <option value="derived">Derived - Computed from other metrics</option>
                                    <option value="aggregate">Aggregate - Accumulated values</option>
                                    <option value="counter">Counter - Simple counting</option>
                                </select>
                            </div>

                            <div class="form-group">
                                <label>Value Type</label>
                                <select name="valueType">
                                    <option value="int">int</option>
                                    <option value="float" selected>float</option>
                                    <option value="bool">bool</option>
                                    <option value="list[int]">list[int]</option>
                                    <option value="list[float]">list[float]</option>
                                </select>
                            </div>

                            <div class="form-group">
                                <label>Unit</label>
                                <select name="unit">
                                    <option value="time">Time (nanoseconds)</option>
                                    <option value="tokens">Tokens</option>
                                    <option value="ratio">Ratio</option>
                                    <option value="count">Count</option>
                                    <option value="throughput">Throughput (per second)</option>
                                </select>
                            </div>

                            <div class="form-group">
                                <label>
                                    <input type="checkbox" name="streamingOnly">
                                    Streaming endpoints only
                                </label>
                            </div>

                            <div class="form-group">
                                <label>
                                    <input type="checkbox" name="largerIsBetter">
                                    Larger values are better
                                </label>
                            </div>
                        </div>

                        <!-- Endpoint-specific config -->
                        <div id="endpointConfig" class="plugin-specific-config" style="display:none;">
                            <div class="form-group">
                                <label>
                                    <input type="checkbox" name="supportsStreaming" checked>
                                    Supports streaming responses
                                </label>
                            </div>

                            <div class="form-group">
                                <label>API Version</label>
                                <input type="text" name="apiVersion" value="v1" placeholder="v1">
                            </div>

                            <div class="form-group">
                                <label>Content Types (comma-separated)</label>
                                <input type="text" name="contentTypes"
                                       value="application/json"
                                       placeholder="application/json, text/event-stream">
                            </div>
                        </div>

                        <!-- Generic config for other types -->
                        <div id="genericConfig" class="plugin-specific-config" style="display:none;">
                            <p>Plugin-specific configuration will be added in the generated code.</p>
                        </div>
                    </div>

                    <!-- Step 4: Review and Create -->
                    <div class="wizard-step" data-step="4">
                        <h2>Review and Create</h2>

                        <div class="review-section">
                            <h3>Plugin Summary</h3>
                            <table class="review-table">
                                <tr>
                                    <td><strong>Type:</strong></td>
                                    <td id="reviewPluginType"></td>
                                </tr>
                                <tr>
                                    <td><strong>Name:</strong></td>
                                    <td id="reviewPluginName"></td>
                                </tr>
                                <tr>
                                    <td><strong>Display Name:</strong></td>
                                    <td id="reviewDisplayName"></td>
                                </tr>
                                <tr>
                                    <td><strong>Package:</strong></td>
                                    <td id="reviewPackageName"></td>
                                </tr>
                                <tr>
                                    <td><strong>Entry Point:</strong></td>
                                    <td id="reviewEntryPoint" class="code"></td>
                                </tr>
                            </table>

                            <h3>Files to be Created</h3>
                            <ul id="filesList" class="files-list"></ul>

                            <div class="aip-badge">
                                <span class="badge">✓ AIP-001 Compliant</span>
                                <span class="badge">📦 Entry Point Discovery</span>
                                <span class="badge">⚡ Lazy Loading</span>
                                <span class="badge">🔒 Type Safe</span>
                            </div>
                        </div>
                    </div>

                    <!-- Navigation Buttons -->
                    <div class="wizard-nav">
                        <button type="button" id="prevBtn" class="btn btn-secondary" disabled>
                            ← Previous
                        </button>
                        <button type="button" id="nextBtn" class="btn btn-primary">
                            Next →
                        </button>
                        <button type="submit" id="createBtn" class="btn btn-success" style="display:none;">
                            🚀 Create Plugin
                        </button>
                    </div>
                </form>
            </div>

            <script src="${scriptUri}"></script>
        </body>
        </html>`;
    }

    public dispose() {
        PluginWizardPanel.currentPanel = undefined;
        this._panel.dispose();

        while (this._disposables.length) {
            const disposable = this._disposables.pop();
            if (disposable) {
                disposable.dispose();
            }
        }
    }
}
