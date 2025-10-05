// SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';

export class GuidebookProvider implements vscode.TreeDataProvider<GuidebookItem> {
    private _onDidChangeTreeData: vscode.EventEmitter<GuidebookItem | undefined | null | void> = new vscode.EventEmitter<GuidebookItem | undefined | null | void>();
    readonly onDidChangeTreeData: vscode.Event<GuidebookItem | undefined | null | void> = this._onDidChangeTreeData.event;

    refresh(): void {
        this._onDidChangeTreeData.fire();
    }

    getTreeItem(element: GuidebookItem): vscode.TreeItem {
        return element;
    }

    getChildren(element?: GuidebookItem): Thenable<GuidebookItem[]> {
        const workspaceFolder = vscode.workspace.workspaceFolders?.[0];
        if (!workspaceFolder) {
            return Promise.resolve([]);
        }

        const guidebookPath = path.join(workspaceFolder.uri.fsPath, 'guidebook');

        if (!fs.existsSync(guidebookPath)) {
            return Promise.resolve([]);
        }

        if (!element) {
            // Root level - return all chapters
            const files = fs.readdirSync(guidebookPath)
                .filter(file => file.endsWith('.md') && file.startsWith('chapter-'))
                .sort();

            return Promise.resolve(files.map(file => {
                const filePath = path.join(guidebookPath, file);
                const title = this.extractTitle(filePath);
                return new GuidebookItem(
                    title,
                    vscode.Uri.file(filePath),
                    vscode.TreeItemCollapsibleState.None
                );
            }));
        }

        return Promise.resolve([]);
    }

    private extractTitle(filePath: string): string {
        try {
            const content = fs.readFileSync(filePath, 'utf8');
            const match = content.match(/^#\s+(.+)$/m);
            if (match) {
                return match[1];
            }
        } catch (error) {
            // Fallback to filename
        }
        return path.basename(filePath, '.md');
    }
}

class GuidebookItem extends vscode.TreeItem {
    constructor(
        public readonly label: string,
        public readonly resourceUri: vscode.Uri,
        public readonly collapsibleState: vscode.TreeItemCollapsibleState
    ) {
        super(label, collapsibleState);
        this.tooltip = this.label;
        this.command = {
            command: 'markdown.showPreview',
            title: 'Open Guidebook Chapter',
            arguments: [this.resourceUri]
        };
        this.iconPath = new vscode.ThemeIcon('book');
    }
}
