# Test Plan

| Rule | Test method | Expected result | Actual | Pass/Fail |
|---|---|---|---|---|
| SSH brute force | Run ssh-brute-force.sh | HIGH alert within 5 min window | | |
| Port scan | Run port-scan.sh | MEDIUM alert | | |
| SQL injection | Run sqli-xss.sh | HIGH alert with decoded payload | | |
| XSS | Manual payload via curl | MEDIUM alert | | |

## Security test of platform (SQLi/XSS/access control on the SOC app itself)
- [ ] Tried SQLi on login form
- [ ] Tried XSS on note/comment fields
- [ ] Tried accessing another analyst's incident without permission
