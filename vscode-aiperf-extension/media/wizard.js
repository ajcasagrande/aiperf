// SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

(function() {
    const vscode = acquireVsCodeApi();

    let currentStep = 1;
    const totalSteps = 4;

    // Initialize wizard
    document.addEventListener('DOMContentLoaded', () => {
        setupNavigation();
        setupFormHandlers();
        updateUI();
    });

    function setupNavigation() {
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');
        const createBtn = document.getElementById('createBtn');

        prevBtn.addEventListener('click', () => {
            if (currentStep > 1) {
                currentStep--;
                updateUI();
            }
        });

        nextBtn.addEventListener('click', () => {
            if (validateCurrentStep()) {
                if (currentStep < totalSteps) {
                    currentStep++;
                    updateUI();
                }
            }
        });

        createBtn.addEventListener('click', (e) => {
            e.preventDefault();
            createPlugin();
        });
    }

    function setupFormHandlers() {
        // Plugin type selection
        const pluginTypeInputs = document.querySelectorAll('input[name="pluginType"]');
        pluginTypeInputs.forEach(input => {
            input.addEventListener('change', handlePluginTypeChange);
        });

        // Auto-fill package name from plugin name
        const pluginNameInput = document.getElementById('pluginName');
        const packageNameInput = document.getElementById('packageName');

        if (pluginNameInput && packageNameInput) {
            pluginNameInput.addEventListener('input', (e) => {
                const value = e.target.value;
                packageNameInput.value = `aiperf-${value}`;

                // Validate name
                vscode.postMessage({
                    command: 'validateName',
                    data: value
                });
            });
        }
    }

    function handlePluginTypeChange(e) {
        const selectedType = e.target.value;

        // Hide all config sections
        document.querySelectorAll('.plugin-specific-config').forEach(el => {
            el.style.display = 'none';
        });

        // Show relevant config section
        const configSection = document.getElementById(`${selectedType}Config`);
        if (configSection) {
            configSection.style.display = 'block';
        } else {
            document.getElementById('genericConfig').style.display = 'block';
        }
    }

    function updateUI() {
        // Update progress steps
        document.querySelectorAll('.progress-step').forEach(step => {
            const stepNum = parseInt(step.dataset.step);
            step.classList.toggle('active', stepNum === currentStep);
            step.classList.toggle('completed', stepNum < currentStep);
        });

        // Update wizard steps
        document.querySelectorAll('.wizard-step').forEach(step => {
            const stepNum = parseInt(step.dataset.step);
            step.classList.toggle('active', stepNum === currentStep);
        });

        // Update buttons
        const prevBtn = document.getElementById('prevBtn');
        const nextBtn = document.getElementById('nextBtn');
        const createBtn = document.getElementById('createBtn');

        prevBtn.disabled = currentStep === 1;

        if (currentStep === totalSteps) {
            nextBtn.style.display = 'none';
            createBtn.style.display = 'inline-block';
            updateReview();
        } else {
            nextBtn.style.display = 'inline-block';
            createBtn.style.display = 'none';
        }
    }

    function validateCurrentStep() {
        const currentStepEl = document.querySelector(`.wizard-step[data-step="${currentStep}"]`);
        const requiredInputs = currentStepEl.querySelectorAll('[required]');

        for (const input of requiredInputs) {
            if (!input.value || (input.type === 'radio' && !document.querySelector(`input[name="${input.name}"]:checked`))) {
                input.focus();
                return false;
            }
        }

        return true;
    }

    function updateReview() {
        const formData = new FormData(document.getElementById('pluginForm'));

        document.getElementById('reviewPluginType').textContent = formData.get('pluginType');
        document.getElementById('reviewPluginName').textContent = formData.get('pluginName');
        document.getElementById('reviewDisplayName').textContent = formData.get('displayName');
        document.getElementById('reviewPackageName').textContent = formData.get('packageName');

        const entryPoint = `[project.entry-points."aiperf.${formData.get('pluginType')}"]\\n` +
                          `${formData.get('pluginName')} = "${formData.get('packageName')}.${formData.get('pluginName')}:PluginClass"`;
        document.getElementById('reviewEntryPoint').textContent = entryPoint;

        // Files list
        const filesList = document.getElementById('filesList');
        const packageName = formData.get('packageName');
        const pluginName = formData.get('pluginName');

        const files = [
            `${packageName}/pyproject.toml - Entry points configuration`,
            `${packageName}/src/${packageName}/__init__.py - Package initialization`,
            `${packageName}/src/${packageName}/${pluginName}.py - Plugin implementation`,
            `${packageName}/tests/test_${pluginName}.py - Test suite`,
            `${packageName}/README.md - Documentation`,
            `${packageName}/LICENSE - Apache 2.0`,
            `${packageName}/.github/workflows/test.yml - CI/CD`,
            `${packageName}/.pre-commit-config.yaml - Code quality hooks`,
        ];

        filesList.innerHTML = files.map(f => `<li><code>${f}</code></li>`).join('');
    }

    function createPlugin() {
        const formData = new FormData(document.getElementById('pluginForm'));
        const pluginConfig = {};

        for (const [key, value] of formData.entries()) {
            pluginConfig[key] = value;
        }

        // Add metadata
        pluginConfig.version = '0.1.0';
        pluginConfig.author = 'Your Name';  // TODO: Get from git config
        pluginConfig.email = 'your.email@example.com';
        pluginConfig.aipVersion = '001';

        vscode.postMessage({
            command: 'createPlugin',
            data: pluginConfig
        });
    }

    // Handle messages from extension
    window.addEventListener('message', event => {
        const message = event.data;

        switch (message.command) {
            case 'validationResult':
                const pluginNameInput = document.getElementById('pluginName');
                if (message.valid) {
                    pluginNameInput.classList.remove('invalid');
                    pluginNameInput.classList.add('valid');
                } else {
                    pluginNameInput.classList.remove('valid');
                    pluginNameInput.classList.add('invalid');
                }
                break;
        }
    });
})();
