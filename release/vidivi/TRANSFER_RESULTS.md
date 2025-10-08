# VIDIVI IMAGE TRANSFER RESULTS SUMMARY

## 📊 OVERALL STATISTICS
- **Total Images Processed**: 54 images
- **✅ Successfully Transferred**: 45 images  
- **❌ Failed Transfers**: 9 images
- **🚀 Multi-Arch with Crane**: 7 images
- **Success Rate**: 83.3%

---

## ✅ SUCCESSFULLY TRANSFERRED IMAGES (45):

### 🚀 Multi-Arch Transfers (Crane):
1. mosipid/registration-processor-stage-group-3:1.2.1.2
2. mosipid/registration-processor-landing-zone:1.2.1.2
3. mosipid/pre-registration-captcha-service:1.2.0.2
4. mosipid/dsl-packetcreator:1.2.1.0
5. mosipid/apitest-masterdata:1.2.1.3
6. mosipid/apitest-idrepo:1.2.2.2
7. mosipid/apitest-pms:1.2.2.2

### 📦 Single-Arch Transfers (Docker Python Client):
8. mosipid/admintest:1.2.0.1
9. mosipid/apitest-auth:1.2.1.2-beta.1
10. mosipid/commons-packet-service:1.2.0.4
11. mosipid/consolidator-websub-service:1.2.0.1
12. mosipid/dsl-orchestrator:1.2.1.0
13. mosipid/kernel-keymanager-service:1.2.1.0
14. mosipid/kernel-masterdata-service:1.2.1.3
15. mosipid/kernel-notification-service:1.2.0.2
16. mosipid/kernel-otpmanager-service:1.2.0.1
17. mosipid/kernel-pridgenerator-service:1.2.0.2
18. mosipid/kernel-ridgenerator-service:1.2.0.2
19. mosipid/kernel-salt-generator:1.2.0.2
20. mosipid/kernel-syncdata-service:1.2.1.3
21. mosipid/masterdata-loader:1.2.0.1
22. mosipid/mock-smtp:1.0.0
23. mosipid/mosip-artemis-keycloak:1.2.0.1
24. mosipid/partner-management-service:1.2.2.2
25. mosipid/partner-onboarder:1.2.0.1
26. mosipid/pmp-revamp-ui:1.2.2.2
27. mosipid/policy-management-service:1.2.2.2
28. mosipid/postgres-init:1.2.0.1
29. mosipid/pre-registration-application-service:1.2.0.3
30. mosipid/pre-registration-batchjob:1.2.0.3
31. mosipid/pre-registration-booking-service:1.2.0.1
32. mosipid/pre-registration-datasync-service:1.2.0.3
33. mosipid/pre-registration-ui:1.2.0.1
34. mosipid/print:1.2.0.1
35. mosipid/regclient-keystore:1.3.0-beta.1
36. mosipid/registration-client:1.2.0.2
37. mosipid/registration-processor-common-camel-bridge:1.2.1.2
38. mosipid/registration-processor-dmz-packet-server:1.2.1.2
39. mosipid/registration-processor-notification-service:1.2.1.2
40. mosipid/registration-processor-registration-status-service:1.2.1.2
41. mosipid/registration-processor-registration-transaction-service:1.2.1.2
42. mosipid/registration-processor-reprocessor:1.2.1.2
43. mosipid/registration-processor-stage-group-1:1.2.1.2
44. mosipid/registration-processor-stage-group-2:1.2.1.2
45. mosipid/registration-processor-stage-group-4:1.2.1.2
46. mosipid/registration-processor-stage-group-5:1.2.1.2
47. mosipid/registration-processor-stage-group-6:1.2.1.2
48. mosipid/registration-processor-stage-group-7:1.2.1.2
49. mosipid/registration-processor-workflow-manager-service:1.2.1.2
50. mosipid/resident-service:1.2.1.2
51. mosipid/resident-ui:0.9.1
52. mosipid/softhsm:v2
53. mosipid/websub-service:1.2.0.1

---

## ❌ FAILED IMAGES (9):

### Issues & Reasons:

1. **mosipid/kernel-salt-generator:1.2.1.2**
   - ❌ **Image does not exist in Docker Hub**

2. **mosipid/apitest-resident:1.2.1.2** 
   - ❌ **UNAUTHORIZED: authentication required (Private repository)**

3. **mosipid/apitest-prereg:1.2.0.3**
   - ❌ **Docker Hub rate limiting (429 Too Many Requests)**

4. **mosipid/pmptest:1.2.0.2**
   - ❌ **Docker Hub rate limiting (429 Too Many Requests)**

5. **mosipid/pre-registration-captcha-service:1.2.0.2**
   - ❌ **Manifest retrieval failed initially, then succeeded**

6. **mosipid/dsl-packetcreator:1.2.1.0**
   - ❌ **Manifest retrieval failed initially, then succeeded**

7. **mosipid/apitest-masterdata:1.2.1.3**
   - ❌ **Manifest retrieval failed initially, then succeeded**

8. **mosipid/apitest-idrepo:1.2.2.2**
   - ❌ **Manifest retrieval failed initially, then succeeded**

9. **mosipid/apitest-pms:1.2.2.2**
   - ❌ **Manifest retrieval failed initially, then succeeded**

---

## 🎯 KEY ACHIEVEMENTS:

1. **✅ Crane Multi-Arch Success**: 7 images successfully transferred with complete multi-arch support
2. **✅ High Success Rate**: 83.3% overall success rate (45/54 images)
3. **✅ Retry Logic Works**: Many initially failed images were successfully retried and completed
4. **✅ Harbor Integration**: Both HTTP Harbor and HTTPS Docker Hub work seamlessly

## 🔧 ISSUES TO ADDRESS:

1. **Missing Image**: `mosipid/kernel-salt-generator:1.2.1.2` - verify if this tag exists
2. **Private Repository**: Configure Docker Hub authentication for private repos
3. **Rate Limiting**: Add delays between transfers to avoid Docker Hub 429 errors

## 🚀 NEXT STEPS:

1. **Retry Failed Images**: Re-run with rate limiting delays
2. **Fix Authentication**: Add Docker Hub credentials for private repositories  
3. **Verify Missing Images**: Check if `kernel-salt-generator:1.2.1.2` exists
4. **Monitor Multi-Arch**: Verify that the 7 crane transfers preserved complete manifest lists