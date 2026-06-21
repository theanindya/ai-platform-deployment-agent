document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('deploymentForm');
    const submitBtn = document.getElementById('submitBtn');
    const submitLoader = document.getElementById('submitLoader');

    // Model catalogue sourced from synthetic registry & security_scans data
    const MODEL_CATALOGUE = {
        'fraud-detection-v2': {
            versions: ['2.0.0', '2.0.1'],
            images: {
                '2.0.0': 'gcr.io/enterprise-platform/fraud-detection:v2',
                '2.0.1': 'gcr.io/enterprise-platform/fraud-detection:v2'
            }
        },
        'fraud-detection-v1': {
            versions: ['1.0.0', '1.1.0'],
            images: {
                '1.0.0': 'gcr.io/enterprise-platform/fraud-detection:v1',
                '1.1.0': 'gcr.io/enterprise-platform/fraud-detection:v1'
            }
        },
        'customer-churn-v3': {
            versions: ['3.0.0', '3.1.0'],
            images: {
                '3.0.0': 'gcr.io/enterprise-platform/customer-churn:v3',
                '3.1.0': 'gcr.io/enterprise-platform/customer-churn:v3'
            }
        }
    };

    const modelSelect = document.getElementById('model_name');
    const versionSelect = document.getElementById('model_version');
    const imageSelect = document.getElementById('container_image');

    function updateVersions(modelKey) {
        const catalogue = MODEL_CATALOGUE[modelKey];
        versionSelect.innerHTML = '';
        imageSelect.innerHTML = '';
        if (!catalogue) {
            versionSelect.innerHTML = '<option value="">-- Select model first --</option>';
            imageSelect.innerHTML = '<option value="">-- Select model first --</option>';
            return;
        }
        catalogue.versions.forEach(v => {
            versionSelect.innerHTML += `<option value="${v}">${v}</option>`;
        });
        updateImage(modelKey, versionSelect.value);
    }

    function updateImage(modelKey, version) {
        const catalogue = MODEL_CATALOGUE[modelKey];
        if (!catalogue) return;
        const img = catalogue.images[version] || Object.values(catalogue.images)[0];
        imageSelect.innerHTML = `<option value="${img}">${img}</option>`;
    }

    modelSelect.addEventListener('change', () => updateVersions(modelSelect.value));
    versionSelect.addEventListener('change', () => updateImage(modelSelect.value, versionSelect.value));


    
    // Panels
    const summaryPanel = document.getElementById('summaryPanel');
    const violationsPanel = document.getElementById('violationsPanel');
    const timelinePanel = document.getElementById('timelinePanel');
    
    // Summary elements
    const verdictBadge = document.getElementById('verdictBadge');
    const verdictReason = document.getElementById('verdictReason');
    const riskPath = document.getElementById('riskPath');
    const riskScoreText = document.getElementById('riskScoreText');
    const riskLevelBadge = document.getElementById('riskLevelBadge');
    
    // Lists
    const violationsTableBody = document.querySelector('#violationsTable tbody');
    const timelineList = document.getElementById('timelineList');

    // Generate random Request ID
    const generateRequestId = () => {
        return 'REQ-' + Math.random().toString(36).substring(2, 9).toUpperCase();
    };

    form.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        // UI Reset
        submitBtn.disabled = true;
        submitLoader.classList.remove('hidden');
        summaryPanel.classList.add('hidden');
        violationsPanel.classList.add('hidden');
        timelinePanel.classList.add('hidden');
        
        // Build Payload
        const formData = new FormData(form);
        const payload = {
            request_id: generateRequestId(),
            model_name: formData.get('model_name'),
            model_version: formData.get('model_version'),
            container_image: formData.get('container_image'),
            target_cluster: formData.get('target_cluster'),
            environment: formData.get('environment'),
            namespace: formData.get('namespace'),
            cpu_request: formData.get('cpu_request'),
            memory_request: formData.get('memory_request'),
            gpu_request: formData.get('gpu_request'),
            monitoring_enabled: formData.get('monitoring_enabled') === 'on',
            rollback_strategy: formData.get('rollback_strategy')
        };

        try {
            const response = await fetch('/deploy', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (!response.ok) {
                throw new Error(`Server error: ${response.status}`);
            }

            const data = await response.json();
            renderResults(data);

        } catch (error) {
            alert('Failed to submit deployment request: ' + error.message);
            console.error(error);
        } finally {
            submitBtn.disabled = false;
            submitLoader.classList.add('hidden');
        }
    });

    function renderResults(data) {
        // 1. Verdict
        const verdict = data.verdict || 'UNKNOWN';
        verdictBadge.textContent = verdict;
        verdictBadge.className = 'badge large';
        
        if (verdict === 'APPROVED') verdictBadge.classList.add('status-APPROVED');
        else if (verdict === 'APPROVED WITH WARNINGS') verdictBadge.classList.add('status-WARNINGS');
        else if (verdict === 'BLOCKED') verdictBadge.classList.add('status-BLOCKED');
        else verdictBadge.classList.add('status-PENDING');

        verdictReason.textContent = data.reason || 'No specific reason provided.';
        
        // 2. Risk Assessment
        const risk = data.risk_assessment || {};
        const score = risk.risk_score || 0;
        const level = risk.risk_level || 'UNKNOWN';
        
        riskScoreText.textContent = score;
        riskPath.setAttribute('stroke-dasharray', `${score}, 100`);
        
        riskPath.className.baseVal = 'circle'; // reset
        if (level === 'LOW') riskPath.classList.add('risk-low');
        else if (level === 'MEDIUM') riskPath.classList.add('risk-medium');
        else if (level === 'HIGH') riskPath.classList.add('risk-high');

        riskLevelBadge.textContent = level;
        riskLevelBadge.className = 'badge small';
        if (level === 'LOW') riskLevelBadge.classList.add('status-APPROVED');
        else if (level === 'MEDIUM') riskLevelBadge.classList.add('status-WARNINGS');
        else if (level === 'HIGH') riskLevelBadge.classList.add('status-BLOCKED');
        else riskLevelBadge.classList.add('status-PENDING');

        summaryPanel.classList.remove('hidden');

        // 3. Violations Table
        // Violations are strings like "[Security] Critical CVE found in base image"
        violationsTableBody.innerHTML = '';
        if (data.violations && data.violations.length > 0) {
            data.violations.forEach(v => {
                const vStr = String(v);
                
                // Extract domain tag e.g. "[Security]"
                const domainMatch = vStr.match(/^\[([^\]]+)\]/);
                const domain = domainMatch ? domainMatch[1] : 'General';
                const message = domainMatch ? vStr.replace(domainMatch[0], '').trim() : vStr;
                
                // Infer severity from keywords
                let severity = 'LOW';
                const lower = vStr.toLowerCase();
                if (lower.includes('critical') || lower.includes('blocked') || lower.includes('high')) {
                    severity = 'HIGH';
                } else if (lower.includes('warning') || lower.includes('medium') || lower.includes('missing')) {
                    severity = 'MEDIUM';
                }

                const tr = document.createElement('tr');
                
                const tdSeverity = document.createElement('td');
                tdSeverity.textContent = severity;
                tdSeverity.className = `severity-${severity.toLowerCase()}`;
                
                const tdDomain = document.createElement('td');
                tdDomain.textContent = domain;
                
                const tdMessage = document.createElement('td');
                tdMessage.textContent = message;

                tr.appendChild(tdSeverity);
                tr.appendChild(tdDomain);
                tr.appendChild(tdMessage);
                violationsTableBody.appendChild(tr);
            });
            violationsPanel.classList.remove('hidden');
        }

        // 4. Timeline
        timelineList.innerHTML = '';
        if (data.trace_events && data.trace_events.length > 0) {
            data.trace_events.forEach(event => {
                // Skip the initial user payload echo if needed, but usually good to show
                const li = document.createElement('li');
                li.className = 'timeline-item';
                
                let details = '';
                if (event.output) {
                    if (typeof event.output === 'object') {
                        // Extract high level info for timeline to keep it clean
                        if (event.output.verdict) details = `Verdict: ${event.output.verdict}\n${event.output.reason}`;
                        else if (event.output.risk_score !== undefined) details = `Risk Level: ${event.output.risk_level} (Score: ${event.output.risk_score})`;
                        else if (event.output.findings) details = `Found ${event.output.findings.length} issues.`;
                        else details = JSON.stringify(event.output, null, 2);
                    } else {
                        details = String(event.output);
                    }
                }

                if (event.error_message) {
                    details += `\nError: ${event.error_message}`;
                }

                li.innerHTML = `
                    <div class="timeline-marker"></div>
                    <div class="timeline-content">
                        <div class="timeline-header">
                            <span class="timeline-author">${event.author}</span>
                        </div>
                        <div class="timeline-details">${details}</div>
                    </div>
                `;
                timelineList.appendChild(li);
            });
            timelinePanel.classList.remove('hidden');
        }
    }
});
