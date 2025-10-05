// SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

export class PluginProvider implements vscode.TreeDataProvider<PluginItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<PluginItem | undefined | null | void> = new vscode.EventEmitter<PluginItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<PluginItem | undefined | null | void> = this._onDidChangeTreeData.event;

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: PluginItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: PluginItem): Thenable<PluginItem[]> {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            return Promise.resolve([]);
        }

        const pluginsPath = path.join(workspaceFolder.uri.fsPath, 'aiperf', 'plugins');

        if (!fs.existsSync(pluginsPath)) {
            return Promise.resolve([]);
        }

        if (!element) {
            // Find all plugin files
            const files = fs.readdirSync(pluginsPath)
                .filter(file => file.endsWith('.py') &&
                               !file.startsWith('__') &&
                               !file.startsWith('example_'));

            return Promise.resolve(files.map(file => {
                const filePath = path.join(pluginsPath, file);
                const pluginName = path.basename(file, '.py');
                return new PluginItem(
                    pluginName,
                    vscode.Uri.file(filePath),
                    vscode.TreeItemCollapsibleState.None,
                    this.detectPluginType(filePath)
                );
            }));
        }

        return Promise.resolve([]);
    }

    private detectPluginType(filePath: string): string {
        try {
            const content = fs.readFileSync(filePath, 'utf8');
            if (content.includes('aiperf.metric')) return 'metric';
            if (content.includes('aiperf.endpoint')) return 'endpoint';
            if (content.includes('aiperf.data_exporter')) return 'data_exporter';
            if (content.includes('aiperf.transport')) return 'transport';
            if (content.includes('aiperf.processor')) return 'processor';
            if (content.includes('aiperf.collector')) return 'collector';
        } catch (error) {
            // Fallback
        }
        return 'unknown';
    }
}

class PluginItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly resourceUri: vscode.Uri,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState,
        public readonly pluginType: string
    ) {
        super(label, collapsibleState);
        this.tooltip = `${this.label} (${pluginType})`;
        this.description = pluginType;
        this.command = {
            command: 'vscode.open',
            title: 'Open Plugin',
            arguments: [this.resourceUri]
        };
        this.iconPath = this.getIcon(pluginType);
        this.contextValue = 'plugin';
    }

    private getIcon(type: string): vscode.ThemeIcon {
        switch (type) {
            case 'metric': return new vscode.ThemeIcon('graph');
            case 'endpoint': return new vscode.ThemeIcon('globe');
            case 'data_exporter': return new vscode.ThemeIcon('export');
            case 'transport': return new vscode.ThemeIcon('plug');
            case 'processor': return new vscode.ThemeIcon('gear');
            case 'collector': return new vscode.ThemeIcon('radio-tower');
            default: return new vscode.ThemeIcon('file');
        }
    }
}
