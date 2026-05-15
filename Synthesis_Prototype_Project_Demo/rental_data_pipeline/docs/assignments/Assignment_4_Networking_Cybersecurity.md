# Assignment 4 - Assessing Networking and Cybersecurity

## Section 1: Self-Assessment

### What I Know: Core Competencies
My proficiency in Networking and Cybersecurity is grounded in the ability to map, monitor, and help secure the infrastructure of an IT environment. Through **CIDM 6340 - Networking Management & Information Security** and **CIDM 6356 - Digital Forensics and Fraud Detection**, I gained a functional understanding of network topology and applied security concepts. This is the pillar where I entered the program with the least prior professional experience, and I will characterize it accurately.

**Networking Competencies:**
* **Network Mapping & Device Discovery:** Identifying active nodes—routers, workstations, IoT devices—within a network and understanding how RFC1918 private address space is organized. In CIDM 6340, I performed a complete scan of a home network and categorized every connected device by type, purpose, and traffic profile.
* **Traffic Analysis:** Using **Wireshark** to capture and inspect packet data. I can distinguish protocol types in a capture, identify traffic on specific ports, and recognize patterns that warrant further investigation—such as unexpected outbound connections or excessive broadcast activity that may signal a misconfigured device or a security concern.

**Cybersecurity Competencies:**
* **Authentication & Access Control Principles:** Understanding how authentication mechanisms—username/password, MFA, and OTP—and role-based authorization controls enforce boundaries around systems and data. The capstone prototype directly implements these: `@login_required` on all views, role-based middleware routing, and OTP two-factor authentication.
* **Secure Protocol Awareness:** Understanding that application traffic must be encrypted in transit via HTTPS/TLS and that credentials must never be stored in plaintext or transmitted without hashing.
* **Security Monitoring Concepts:** Recognizing that security is an ongoing posture, not a one-time configuration—authentication events should be logged, access anomalies should be detected, and permission structures should be audited regularly.

*Note: Digital forensics (chain of custody) and fraud detection algorithms are adjacent competencies developed in CIDM 6356. While they inform my analytical thinking about data integrity, they are not core networking or security administration skills and are listed here for accuracy rather than as primary evidence of CN proficiency.*

### Where I am Weak: Areas for Growth
This is the pillar where I have the most ground to cover. My gaps span both the networking and cybersecurity sides of the field.

**Networking Gaps:**
* **Enterprise Topology Design & Subnetting at Scale:** I can work with small home or office IP ranges but lack the fluency to design segmented enterprise networks—defining VLANs, security zone subnets, or address plans that support hundreds of devices across multiple sites.
* **Deep-Packet Inspection & Advanced Log Analysis:** I can read basic Wireshark captures, but interpreting noisy, encrypted, or high-volume traffic to reach a specific security conclusion remains a significant challenge.

**Cybersecurity Gaps:**
* **Identity and Access Management (IAM) at Scale:** I can implement role-based access within a single application, but I have no experience with enterprise IAM platforms, directory services (Active Directory, LDAP), or federated identity systems.
* **Security Information and Event Management (SIEM):** I have no hands-on experience with SIEM tooling such as Splunk or Microsoft Sentinel. Given that security operations depend on centralized log aggregation and correlation, this is a fundamental gap.
* **Vulnerability Management & Secure Configuration:** I have not performed formal vulnerability assessments, applied hardening checklists against frameworks like CIS Benchmarks, or managed a patching and remediation cycle.
* **Regulatory Frameworks & Policy Design:** While I understand that NIST, ISO 27001, HIPAA, and GDPR impose real requirements on security architecture, I have not applied any of these frameworks in practice or written security policies that translate technical controls into enforceable organizational behavior.

### What I Wish I Knew: The Strategic Gap
Proactive Threat Hunting and Zero Trust Architecture are legitimate strategic goals, but the deeper realization is how much of modern cybersecurity I had not even identified as a domain until I looked outside of coursework.

**The evolving threat landscape I was not tracking:**
Reviewing cybersecurity industry publications revealed concerns that were entirely absent from my academic frame: **software supply chain risk** (the SolarWinds and Log4j incidents demonstrate that modern attacks increasingly enter through trusted dependencies, not direct infiltration), **cloud-native and container security** (securing Kubernetes workloads, managing secrets in CI/CD pipelines, and ensuring container images are hardened against known vulnerabilities), and **AI-assisted threats** (adversarial use of language models for phishing content generation and social engineering at scale). These are not edge concerns—they are mainstream challenges in current enterprise security.

**The human and organizational dimension I underestimated:**
The most significant blind spot I discovered is that the majority of security failures are not purely technical—they are human and organizational. **Social engineering**, phishing resistance, and **security culture** are dimensions that no firewall rule addresses. An organization can have technically excellent access controls and still suffer a breach because one employee was deceived into sharing credentials. **Insider risk**—the possibility that authorized users themselves are the threat vector—requires behavioral monitoring and policy enforcement that operates entirely outside the technical security toolkit. I had barely considered this dimension before reflecting on it for this assignment.

---

## Section 2: Supporting Evidence 

### Samples of Work: Professional and Academic Artifacts
My work in **Networking and Cybersecurity** has focused on the visibility and integrity of the data path. Below are representative samples of my technical engagement:

* **Network Topology Audit:** I performed a comprehensive scan of a local network to map every connected device, ensuring no "shadow IT" was present.

    **Network Scan Snapshot (CIDM 6340):**

    | IP Address | Device |
    |---|---|
    | 10.0.0.1 | Router (Gateway) |
    | 10.0.0.67 | Laptop Computer |
    | 10.0.0.27 | Samsung Smart TV |
    | 10.0.0.71 | Firestick 2 |
    | 10.0.0.196 | Firestick 1 |
    | 10.0.0.140 | Nintendo Switch |
    | 10.0.0.61 | Girlfriend's iPhone |
    | 10.0.0.18 | Business Phone |
    | 10.0.0.178 | Personal iPhone |
    | 10.0.0.14 | Personal PC |
    | 10.0.0.136 | Xbox |
    | 10.0.0.79 | Roku TV |
    | 10.0.0.4 | Ford Escape |
    | 10.0.0.81 | Ring |
    | 10.0.0.248 | Apple Watch |

    *Security note: Publishing an IP-to-device inventory from a real network in a public repository, even when addresses are RFC1918 private space, is not ideal security hygiene—it exposes device inventory and network structure. In future portfolio work, this artifact would be sanitized or replaced with a clearly fictional lab-only topology.*

* **Capstone Security Implementation (CIDM 6395):** The rental data pipeline application demonstrates applied security architecture: all views are protected by `@login_required`, a custom `VendorPortalMiddleware` enforces role-based routing at the middleware layer before any view logic executes, OTP two-factor authentication is fully implemented and active for all accounts, and vendor data is isolated by company name at every query to prevent cross-vendor data access. Available at the [CIDM-6395 GitHub Repository](https://github.com/alelawsoWTAMU/CIDM-6395-Alexander-Lawson) as a directly inspectable security artifact.
* **Fraud Detection Website:** In **CIDM 6356**, I contributed to a project focused on the auditing and detection of fraudulent data, managed via GitHub ([Fraud Detection Website](https://github.com/wtamucis/fraud-detection-website-alelawsoWTAMU)).
* **Forensic Data Wrangling:** In **CIDM 6356**, I utilized Google Colab to process extremely large and complex forensic datasets to maintain a clear chain of custody ([Credit Card Fraud Detection: A Comparison of Three Machine Learning Algorithms](https://colab.research.google.com/drive/1LbHiM6zklOAuDK-8KGezcRUfI6tumZgt)).

### Consulted Sources: Sources of Knowledge
* **Academic Labs:** I utilized the **CIDM 6340** curriculum to understand network management and the use of **Wireshark** for packet analysis.
* **Digital Forensics Frameworks:** My understanding of data wrangling and forensic integrity was built through the **CIDM 6356** course materials.
* **Security Tools:** I utilized Google Colab for running advanced fraud detection algorithms.

### Summary Statement
I am a **Guardian of the Infrastructure**—and I hold that identity with appropriate humility. My capabilities in this pillar are real but foundational: I can map a network, read a packet capture, apply access control principles, and reason about security architecture at a conceptual level. The capstone prototype demonstrates applied security practice: `@login_required` on all views, role-based middleware that prevents vendors from accessing reviewer or admin pages, and OTP two-factor authentication that is active and functional. However, I do not yet have the operational depth to act as an independent security lead for an enterprise system. What I bring is accurate self-awareness, an honest accounting of my current level, and the engineering discipline to implement security controls correctly when I understand what they should be.

### Capstone Preparedness
Regarding the Capstone prototype project, my Networking and Cybersecurity knowledge contributed to concrete security decisions in the application's architecture: all views are protected by `@login_required`, a custom `VendorPortalMiddleware` enforces role-based routing that prevents vendors from accessing reviewer or admin pages, OTP two-factor authentication is implemented and active for all accounts, and vendor data is isolated at the query level so that no vendor can access another's records. These are implemented controls, not aspirational claims. What I cannot yet provide independently is a full threat model, a penetration test, or enterprise IAM integration. The security posture of the capstone is appropriate for a controlled demo environment; production hardening would require dedicated security engineering expertise.

---

## Section 3: Integration 

### Why Networking & Cybersecurity is Integratable
Networking and Cybersecurity serve as the **"Nervous System"** of the IT organism. It is the connective tissue that allows the other three pillars to function. Without the network, software cannot communicate, data cannot be managed in a central repository, and analytics has no "live" feed to interpret. Cybersecurity ensures the "health" of this system, protecting the skeleton (Management) and the muscle (Software) from external threats.

### How Networking & Cybersecurity is Integratable
The technical "handshake" occurs through:
* **Software Integration:** Applications must be hosted on specific network ports and secured via protocols like HTTPS.
* **Management Integration:** Databases are accessed over the network; cybersecurity ensures that only authorized software can touch the data.
* **Analytics Integration:** Networking provides the real-time logs (the "senses") that Analytics then interprets into a visual story for leadership.

### How it Integrates with Prior Work
Prior to this program, the network was "magic"—it either worked or it didn't. Now, I understand the underlying IP mapping and the digital envelopes that move data. In my professional role, I have moved from just using hardware to understanding its footprint on the network and how to monitor that traffic for resource usage and security.

### The "Big Picture" Statement
The amalgamation of these four areas results in a living, breathing organism. In this model, **Networking and Cybersecurity** provide the nervous system and the immune system. The network moves data instantaneously, while security ensures the organism remains protected. My capstone will demonstrate this by building a secure interface that utilizes these network "senses" to feed a robust data skeleton, ultimately processed by the analytical brain to drive plant strategy.
