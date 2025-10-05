// SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import * as vscode from 'vscode';
import { PluginWizardPanel } from './wizardPanel';
import { GuidebookProvider } from './guidebookProvider';
import { PluginProvider } from './pluginProvider';

export function activate(context: vscode.ExtensionContext) {
    console.log('AIPerf Developer Tools extension activated');

    // Register plugin wizard command
    context.subscriptions.push(
        vscode.commands.registerCommand('aiperf.createPlugin', () => {
            PluginWizardPanel.createOrShow(context.extensionUri);
        })
    );

    // Register guidebook command
    context.subscriptions.push(
        vscode.commands.registerCommand('aiperf.openGuidebook', () => {
            const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
            if (workspaceFolder) {
                const guidebookPath = vscode.Uri.joinPath(
                    workspaceFolder.uri,
                    'guidebook',
                    'INDEX.md'
                );
                vscode.commands.executeCommand('markdown.showPreview', guidebookPath);
            }
        })
    );

    // Register tree view providers
    const guidebookProvider = new GuidebookProvider();
    vscode.window.registerTreeDataProvider('aiperf.guidebook', guidebookProvider);

    const pluginProvider = new PluginProvider();
    vscode.window.registerTreeDataProvider('aiperf.plugins', pluginProvider);

    // Status bar
    const statusBarItem = vscode.window.createStatusBarItem(
        vscode.StatusBarAlignment.Left,
        100
    );
    statusBarItem.text = '$(beaker) AIPerf';
    statusBarItem.tooltip = 'Click to create AIPerf plugin';
    statusBarItem.command = 'aiperf.createPlugin';
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);
}

export function deactivate() {
    console.log('AIPerf Developer Tools extension deactivated');
}
