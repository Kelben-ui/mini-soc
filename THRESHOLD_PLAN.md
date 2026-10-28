# Threshold recommendations

Based on NIST SP 800-61 guidance and typical SOC detection patterns:

## Rules that should have thresholds

1. **WEB-SQLI-001** (SQL Injection) - HIGH severity, Initial Access
   - Add threshold: count 3 in 60s grouped by src_ip to catch automated scanning/exploitation
   - Rationale: Single attempt might be false positive; repeated attempts indicate attack

2. **WEB-XSS-001** (XSS) - MEDIUM severity  
   - Add threshold: count 3 in 60s grouped by src_ip
   - Rationale: Similar to SQLi, prevent noise from single attempts

3. **WEB-CMD-001** (Command Injection) - HIGH severity
   - Add threshold: count 2 in 60s grouped by src_ip (more sensitive)
   - Rationale: Command injection is serious, even single attempts warrant attention but threshold helps

4. **WEB-LFI-001** (Directory Traversal/LFI) - HIGH severity
   - Add threshold: count 3 in 60s grouped by src_ip
   - Rationale: Directory traversal often part of reconnaissance

5. **WEB-SCAN-001** (Scanner UA) - MEDIUM severity (Reconnaissance)
   - Add threshold: count 5 in 120s grouped by src_ip (or just rely on volume)
   - But it's a specific indicator - maybe threshold count 1 is fine as-is? Or count 3

6. **NET-PORTSCAN-001** - Already works as-is? It comes from IDS detecting port scan. The rule matches action port_scan. Thresholds might be redundant if IDS already thresholds.

7. **IDS-SIG-001** - Generic IDS signature alerts; may need thresholding by signature type?

8. **NET-OUTBOUND-001** - Unusual outbound connections
   - Add threshold: count 3 in 300s grouped by src_ip to catch beaconing
   - Or keep as single event (data exfiltration could be single large transfer)

9. **DNS-ANOMALY-001** - Already has threshold (count 100 in 60s grouped by src_ip) but syntax issue: `-src_ip` missing space?

Also fix DNS-ANOMALY-001 threshold syntax.
