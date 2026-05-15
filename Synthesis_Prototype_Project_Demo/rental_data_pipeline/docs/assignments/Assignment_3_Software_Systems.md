# Assignment 3 - Assessing Software Systems

## Section 1: Self-Assessment

### What I Know: Core Competencies
My strength in software systems lies in **Application Architecture**, **Full-Stack Development**, and **Backend Automation**. Through **CIDM 6303**, I mastered the technical foundations of CIS, focusing on the logic required for data-driven applications. In **CIDM 6325**, I developed strong proficiency in the **Django** framework and the Model-View-Template (MVT) architecture—not just building views and templates, but reasoning about where to place logic: what belongs in the model layer, what belongs in the view, and what belongs in the template.

Professionally, I am highly confident in **C# development**, particularly in building **Windows Services** and full-stack web applications. My capabilities extend beyond knowing languages to applied engineering practices:
* **Separation of Concerns & Layered Architecture:** I design applications with clear boundaries between data access, business logic, and presentation. In the Django capstone, this is demonstrated by the separation of ORM models from view logic from template rendering, with custom middleware handling cross-cutting concerns like role-based routing independently from individual views.
* **Role-Based Access Control Design:** I have implemented RBAC in production using `@login_required` decorators, custom middleware that enforces role routing before requests reach view logic, and OTP-based two-factor authentication.
* **Backend Services & Database Integration:** Experienced writing services that poll live data and synchronize with SQL databases, and building Django management commands for automated operational tasks such as cycle advancement and compliance audit generation.
* **SDLC & Documentation:** Comfortable with **Git/GitHub** for version control, and with architectural documentation practices including ADRs, PRDs, and implementation plans.

These capabilities are *professionally functional* rather than fully production-hardened: the applications solve real business problems, but depth in automated testing, deployment pipelines, and long-term maintainability is still developing—and I will say so directly rather than overstating readiness.

### Where I am Weak: Areas for Growth
While I can build functional tools that solve real problems, I have meaningful gaps in engineering rigor—the difference between *making something work* and *making something maintainable, testable, and deployable*:
* **Automated Testing:** I have not built comprehensive test suites alongside my applications. I understand unit and integration testing conceptually, but I have not developed the habit of writing tests before or alongside code rather than after the fact. This is a gap I consider significant.
* **Deployment & Environment Management:** My applications have run locally or on internal intranet servers. I have no experience with containerization, environment parity between development and production, or deployment pipeline configuration.
* **Observability & Logging:** I do not yet have a disciplined approach to application logging, error monitoring, or alerting. My applications either succeed silently or produce unstructured exception output—there is no structured log strategy or health monitoring in place.
* **Long-Term Maintainability:** I have built applications that work, but I have not been responsible for maintaining them across multiple years, managing accumulated technical debt, or writing them with future contributors in mind.
* **Code Review:** I have not participated in formal peer code review processes, which means I lack the external feedback loops that improve design quality, security posture, and readability over time.

### What I Wish I Knew: The Strategic Gap
I wish to move beyond local deployment into a deeper understanding of production systems engineering, but the more significant insight is that my blind spots are not just technical—they are structural.

**What I did not realize I was missing:**
* **Observability as infrastructure:** Production systems are not watched by humans; they are monitored by automated tools. Structured logging, metrics collection, and alerting are not optional additions—they are how engineering teams know a system is healthy. This concept was entirely absent from my academic software development experience.
* **Technical debt as a managed cost:** I had thought of "imperfect code" as something to fix when time permitted. Professional software engineering treats technical debt as a real cost that accumulates interest and constrains future work; architectural decisions must explicitly account for it.
* **Team-scale conventions:** My entire software background is solo development. In collaborative environments, naming standards, review gates, branching strategies, and documentation requirements are coordination mechanisms, not stylistic preferences. I have no practice operating within them.
* **Infrastructure as Code:** The concept that server configurations, environment variables, and deployment instructions should be version-controlled artifacts—not tribal knowledge—was not part of my academic training at all. Discovering tools like Docker and GitHub Actions during the capstone made clear how much of the engineering discipline I had not yet encountered.

---

## Section 2: Supporting Evidence 

### Samples of Work: Professional and Academic Artifacts
* **Windows Service (C#):** Developed a custom service to pull live energy prices and update a SQL DB in real-time.
* **Corporate Intranet Sites:** Built a suite of full-stack sites using C# and ASP.NET Core Razor Pages, JavaScript, and SQL for the plant's Central Spares (CPS) warehouse and motor management operations. Screenshots are included in this folder:
  * `CPS_Home_Page.jpg` — Consolidated contacts, operational links, and real-time weather into a single-pane portal replacing fragmented manual lookups.
  * `CPS_Item_Library.jpg` — Searchable inventory of 19,700+ parts with daily SQL sync, bin locations, and visual item image library.
  * `CPS_Storage_Request_Form.jpg` — Digital request workflow for internal mill pickups and external vendor deliveries, with automated validation and dual email confirmation.
  * `Motor_Management_Quick_Search.jpg` — Specialized search portal for 3,600+ motors with granular filtering by Frame, HP, Voltage, and RPM; daily SQL refresh.
* **Automation Scripts:** Developed **C# and Python** scripts to auto-generate Excel lineup files and KPI reports, significantly reducing manual administrative labor.
* **Homestead Compass (CIDM 6325):** A Django-based web application for CIDM 6325. The project was a customized work order tracking & scheduling system for a standard American household.

### Consulted Sources: Sources of Knowledge
* **Academic Foundations:** Built the technical foundation through the **CIDM 6303** curriculum, focusing on Python logic and Pandas data manipulation.
* **Technical Documentation:** Regularly utilize the [Django Project Documentation](https://docs.djangoproject.com) and the [Microsoft .NET C# Guide](https://learn.microsoft.com/en-us/dotnet/csharp/).
* **Generative AI:** Leverage MS Copilot for optimizing script logic and debugging full-stack code.

### Summary Statement
I am an **Integrator** who builds "Bridge Applications." My capability is defined by the agility to take a business requirement—like a warehouse search need or a KPI reporting bottleneck—and quickly build a functional C# or Python solution. I capitalize on my ability to link software logic with data management to create tools that are not just functional, but operationally essential.

### Capstone Preparedness
I am fully prepared to lead the **Software Pillar** of the Capstone. I will utilize **Django** for the project interface while drawing on my experience with **Python/Pandas** (from CIDM 6303) to handle the underlying data logic.

---

## Section 3: Contribution Towards the Capstone

### Why Software Systems is Integratable
Software is the **"Action Layer."** While Networking moves data and Management stores it, the Software System is what makes that data interactive and actionable for the end-user.

### How Software Systems is Integratable
The technical "handshake" occurs through:
* **Database Integration:** Using C# or Django Models to create a direct link to the SQL "Skeleton."
* **Analytics Integration:** Using Python/Pandas to process data into the "Brain" (the visuals) for the user.
* **Network Integration:** Hosting applications via web servers that listen on specific ports provided by the "Nervous System."

### Prior Work Connection
Prior to this program, I was a software "user." Now, I am a **creator**. My professional experience has shifted from entering data into a CMMS to building the very services and scripts that automate that data's flow, ensuring higher quality and efficiency.

### The "Big Picture" Statement
If the Network is the nervous system and the Database is the skeleton, **Software is the Muscle**. It provides the strength and movement necessary to perform work. My capstone will demonstrate that I can build the "muscle" (the app) that uses the "vision" (analytics) to solve real-world operational problems.
