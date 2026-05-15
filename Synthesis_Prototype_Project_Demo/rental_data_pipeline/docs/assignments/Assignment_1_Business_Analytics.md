# Assignment 1 -  Assessing Data Analytics

## Section 1: Self-Assessment

### What I Know: Core Competencies
My strongest proficiency lies in the visual delivery of business intelligence. Through my graduate study via **CIDM 6312** and **CIDM 5310**, and my professional responsibilities, I have mastered UI layout and design consistency. I am highly confident building BI Dashboards in both **Tableau** and **Power BI** that prioritize Data Visualization Best Practices. I excel at identifying KPI metrics, constructing data visuals, and using storytelling to ensure that charts provide a clear narrative rather than just a collection of numbers.

Most of this work I perform independently from scratch. For example, when plant leadership needed to justify a contractor workforce strategy, the **Contractor Workforce Monitoring Report** I built provided a rolling 12-week swipe-based headcount trend that answered the business question directly—no template, no external assistance. Where I rely on reference support is in advanced DAX expressions and context-transition logic; the standard KPI layout and storytelling decisions are independently grounded. The distinction matters: my design and communication capability is genuinely autonomous, while my back-end formula engineering still benefits from documentation.

### Where I am Weak: Areas for Growth
Despite my design strengths, I face technical hurdles with the "back-end" of these tools. I am least confident in writing complex **DAX Scripting** for Power BI—specifically context-transition logic and iterator functions like `CALCULATE` with multiple overlapping filter arguments. I often struggle with **Mobile Screen Layouts** for data-heavy reports. When datasets grow beyond several hundred thousand rows, Power BI refresh times increase and DAX-dependent measures begin to lag; diagnosing whether the root cause is measure design, data model cardinality, or query folding limitations is an area where I still need substantially more practice.

Stylistically, I sometimes battle the urge to add **"too much flair."** In practice, this shows up as overusing color gradients, adding secondary axes when they are not analytically necessary, or layering too many visual objects on a single report page—all of which make it harder to identify the primary KPI at a glance. I am actively calibrating toward the principle that a strong dashboard removes distractions rather than adding them.

### Missing Knowledge: The Strategic Gap
To become a "complete" analyst, I need to bridge the gap between Description and Prescription. In my current role with plant leadership, I am highly proficient at accumulating and displaying data to answer "What is this?" However, I am rarely asked "What should we do with this?"

Reviewing senior analyst job postings and examining the portfolios of more advanced peers has revealed a gap I had not fully articulated: the expectation that an analyst will not only present historical data but proactively drive the conversation with **forward-looking recommendations**. The specific skills I am missing are: **time-intelligence forecasting** (using Power BI's DAX time functions or Python integration to project trends forward), **hypothesis testing** (statistically validating whether a performance change is meaningful signal or routine variation), **prescriptive trend interpretation** (not just "costs went up" but "here is the inflection point and the probable cause"), and **scenario analysis** (modeling "what if" outcomes to support leadership decisions before they are made).

My plan to close this gap is concrete: I intend to develop DAX-based time-intelligence measures for period-over-period forecasting, and to leverage Power BI's Python visual integration to incorporate basic statistical testing directly into my dashboards.

---

## Section 2: Supporting Evidence 

### Samples of Work: Professional and Academic Artifacts
My professional work is anchored by a comprehensive suite of Power BI reports developed for senior leadership. The **Equipment Rental Analytics Portfolio**, for example, involves a full ETL (Extract, Transform, Load) workflow, where I manually consolidate disparate vendor data into a unified database table weekly, providing real-time asset oversight. Screenshots of three views from this report are included in this folder as direct evidence of the work:

* **`Cost Over Time.png`** — A line chart tab tracking weekly rental spend across 757 active equipment units, spanning July 2025 through February 2026, with labeled data points showing cost-per-week fluctuations for senior leadership trend analysis.
* **`Weekly Delta.png`** — A comparison tab showing equipment going on and off rent in the current week, with a net delta of -$5,990 highlighted, enabling the rental coordinator to immediately identify cost movement without manual calculation.
* **`Raw Data.png`** — The underlying tabular data view, displaying individual rental records by division, department, cost center, PO number, vendor, and equipment type — the raw layer that feeds all visual tabs.

Similarly, the **Contractor Workforce Monitoring Report** processes "swipe" data to calculate headcounts and visualize trends for the Senior Plant GM. A screenshot of this report is included in this folder (`Contractor_Workforce_Monitoring_Report.jpg`) — it shows 1,008 average headcount per weekday, total site hours, and a rolling headcount-over-time trend from January 2024 through February 2026 across 20+ active contractors. The **Warehouse Operations KPI Dashboard** provides critical trend analysis via daily snapshots, enabling proactive resource allocation when backlogs are high. Screenshots of two tabs from this suite are included (`Warehouse_KPI_Receipts_Daily.jpg` — Receipts Entered Daily by employee and turn; `Warehouse_KPI_Picklist_Inventory.jpg` — Daily Picklist Values and live Inventory Value tracking a $62.8M asset pool). A related **PM Compliance Dashboard** (`PM_Compliance_Dashboard.jpg`) tracks Preventative Maintenance work order completion rates across facility shops from 2023 to present, serving as a direct accountability tool for plant leadership. Finally, the **CMMS Security & User Audit System** serves as a high-speed Decision Support System, allowing me to instantly answer complex administrative queries as the primary plant contact; a screenshot (`CMMS_Security_User_Audit_System.jpg`) shows the TabWare Users Summary with 968 active resource profiles, filterable by department.

These professional projects were complemented by academic training through guided courses via WTAMU in Power BI and Tableau, which taught me to select the right visual encodings, create actionable narrative arcs for non-technical audiences, and move beyond basic charting into deeper exploratory analysis.

### Consulted Sources: External Sources Utilized

*   **Technical Documentation & Community:** To resolve specific hurdles in DAX scripting and dashboard interactivity, I frequently consult official [Microsoft Power BI Documentation](https://learn.microsoft.com/en-us/power-bi/) and the [Tableau Training Gallery](https://www.tableau.com/learn/training). I also frequently use search engines and chat forums if I am stuck on a specific problem.

### Summary Statement
My professional identity is defined by the ability to bridge the gap between complex industrial data and executive decision-making. These skills are not merely theoretical; they are literally how I earn my living. Through my work with plant leadership and my graduate studies, I have developed the propensity to take a wide variety of datasets—whether from CMMS audits or vendor rental logs—and synthesize them into intuitive, high-impact Business Intelligence ecosystems. In my future career, I plan to leverage these capabilities to move beyond reactive reporting into prescriptive analytics, using data storytelling to not only explain what has occurred but to provide the strategic roadmaps necessary for operational optimization. In short, I will utilize my analytics and business intelligence tools to tell stories and ruthlessly eliminate inefficiencies in my work environment. Going forward, the further sharpening of these skills ought to make me a valuable asset for any employer I might have.

### Capstone Preparedness
Regarding the Capstone prototype project, my proficiency in Data Analytics makes the "Interface" element of the project straightforward. I have the technical agility to serve as my own architect, ensuring that the outputs from the networking, software, and data management pillars are translated into a cohesive, "slick" dashboard without requiring external support.

---

## Section 3: Integration 

### Why Data Analytics is Integratable
Data Analytics serves as the critical "narrative layer" that makes the other three curricular areas have real, tangible value. While Networking provides the infrastructure to move data, Data Management provides the architecture to store it, and Software Systems provide the platform to host it, Analytics is the only area that translates those technical logs and raw tables into a language a human can understand: a story. All the infrastructure, databases, and programs in the world are useless to a final decision maker if they cannot actually be used to solve the problems at hand. Data Analytics is integratable because it is sum conclusion of all the others; for example, my professional work as a CMMS primary contact demonstrates that software (the system), the networking (how that information moves from point A to point B) and management (the user database) are essentially invisible until Analytics tells us what it all means.

### How Data Analytics is Integratable (The Technical "Handshake")
The technical integration of Analytics relies on the ETL (Extract, Transform, Load) process. In my MS CISBA coursework and professional projects, the "handshake" occurs when I use Power Query to connect to SQL databases (Management) or API/CSV logs from hardware (Networking/Software). By "corralling" these disparate technical outputs into a unified Power BI Relational Model—creating a "single source of truth"—I transform raw data (the "blob") into organized, visual intelligence that can be consumed by the Senior Plant GM and other plant personnel.

### Prior Work Connection
Before entering the MS CISBA program, my work was largely manual and reactive. Early assignments in this curriculum, paired with my professional projects, allowed me to automate these connections. I moved from simply "finding data" to building automated, complex ecosystems that refresh regularly. This shift has empowered me to manage even larger datasets and more complex questions than was previously possible in my role. The final products, my dashboards, are now more consistent, dynamic, and proactively try to answer questions before they are even asked.

### The "Big Picture" Statement
The amalgamation of these four areas result in a living, breathing organism. In this model, Software ("the muscle") does the heavy lifting of gathering and generating the data through daily transactions and operations. The Network ("the nervous system") moves that data instantaneously to wherever it needs to go, ensuring every part of the organization is connected. Data Management provides the structural memory for storing that data ("the skeleton"), giving the organism a rigid, reliable frame to hold its information. Finally, Analytics provides the vision ("the brain") to understand and utilize that data to solve problems and drive strategy.

My capstone project will demonstrate this by using the Data Transformation skills mastered through hard won experience, professionally and academically, to clean messy technical logs and database entries and presenting them in a "slick" user interface. By integrating these areas, I prove that a "complete" analyst doesn't just provide data—they provide the strategic roadmap to provide actionable insights for their audience.
