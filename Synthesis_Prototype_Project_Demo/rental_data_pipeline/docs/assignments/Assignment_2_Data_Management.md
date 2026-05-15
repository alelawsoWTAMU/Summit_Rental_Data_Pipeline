# Assignment 2 - Assessing Data Management

## Section 1: Self-Assessment

### What I Know: Core Competencies
My proficiency in Data Management is centered on the ability to architect and query relational databases to solve organizational problems. Through **CIDM 6350**, I gained a strong command of **SQL (Structured Query Language)**, specifically in writing complex joins and managing data integrity. I am highly confident in:
* **Schema Design & ETL Mapping:** Creating logical data structures and mapping how information moves from source to destination. For example, in designing the capstone project's relational model, I produced four normalized tables—`rental_staging`, `rental_master`, `vendor_audit`, and `equipment_market_rate`—each communicating via foreign keys, with clear separation between unverified vendor submissions, audited master records, compliance tracking, and reference data.
* **Data Manipulation:** Performing CRUD operations—Create, Read, Update, Delete—to maintain accurate records, such as updating employee information or managing supplier lists.
* **Relational Integrity:** Implementing rules and constraints—`NOT NULL`, `UNIQUE`, `FOREIGN KEY`—to ensure data consistency across multiple tables and prevent orphaned or duplicate records.
* **Data Preparation:** Using **R/RStudio** to clean raw data, handle missing values, and standardize formats so that data is correctly structured before entering a relational database. This is a data management step—getting data ready for reliable storage—distinct from the analytical mining that occurs downstream.

### Where I am Weak: Areas for Growth
While I can write functional queries, I face real hurdles in **performance diagnosis**. When a query is slow, I can identify the symptom more easily than the cause—I struggle to determine whether the root issue is a missing index, a poorly structured JOIN, a lack of query folding, or a data model design decision that creates high-cardinality problems. Additionally:
* **Complex Subqueries & Window Functions:** I am less confident when nested subqueries, recursive CTEs, or SQL window functions are required to produce analytical summaries within a single statement.
* **Data Governance & Lifecycle Management:** I have little hands-on experience with formal data governance practices—defining data ownership, enforcing quality standards at ingestion, managing retention schedules, or maintaining metadata catalogs. These are standard enterprise DM responsibilities that my academic training did not deeply cover.
* **Backup, Recovery, and Permissions at Scale:** While I understand the concepts, I have no production experience managing backup schedules, point-in-time recovery, or role-based permission structures across a multi-user database environment.
* **NoSQL and Cloud Data Platforms:** I have no meaningful hands-on experience with document databases, columnar stores, or cloud data warehouse platforms such as Snowflake, BigQuery, or Azure Synapse—a significant gap given how central these are to modern data engineering.

### What I Wish I Knew: The Strategic Gap
I recognize a gap in pipeline automation, but the deeper blind spot is how much of production data management lies entirely outside the SQL and ETL work I learned in coursework.

Researching professional data management roles revealed disciplines I had not previously considered as part of the field: **data lineage** (tracking exactly where each data element originated, how it was transformed, and where it flows downstream), **data contracts** (formal schema and reliability agreements between the teams that produce and consume data), **data observability** (monitoring pipelines for freshness, completeness, and anomalies the way a software team monitors application uptime), and **disaster recovery planning** (designing for what happens when a database fails, not merely performing backups). These are not advanced specializations—they are baseline expectations for production data engineers and architects.

Additionally, the regulatory dimension surprised me: GDPR, HIPAA, and CCPA impose specific requirements on how data is stored, accessed, retained, and deleted that have no analog in academic SQL exercises. I was not aware until I looked outside of coursework how directly these compliance frameworks constrain schema design choices, retention policies, and access control decisions. This is a genuine blind spot—I did not know this dimension existed at the scale it does until I encountered it.

---

## Section 2: Supporting Evidence 

### Samples of Work: Professional and Academic Artifacts
My work in **CIDM 6350** and **CIDM 6355** provided the technical foundation for my data management skills. Below is a representative sample of SQL tasks I mastered, including data insertion and conditional updates that ensured database reliability:

These academic skills were applied directly in a professional context through a **C# automation script** (`Rental_Vendor_Insert`) that I built for the plant BI environment. The script reads weekly vendor rental data from a shared Excel workbook on the plant network (via **ClosedXML**) and executes a row-by-row INSERT into the corporate SQL Server database (`[HIDDEN]`) using `System.Data.SqlClient`. This eliminated a previously manual data-entry process and directly demonstrates the ETL pipeline skills developed in this pillar—data extraction from a source file, transformation via column mapping, and load into a relational target table. The SQL INSERT statement powering this automation is archived in `professional_rental_vendor_insert.sql`.

```sql
-- Task: Inserting new employee records 
INSERT INTO Employees (LastName, FirstName, BirthDate) 
VALUES ("Avaya", "Bates", "1987-01-01"), ("Don", "Bains", "1969-12-05");

-- Task: Updating specific records based on unique identifiers 
Update Employees Set BirthDate = "1968-01-30" Where EmployeeID = 1;

-- Task: Standardizing data for reporting consistency 
Update Customers Set Country = "United States of America" Where Country = "USA";
```

In addition to SQL, my academic training in **Data Mining Methods** involved using R to manage and analyze metropolitan datasets. I successfully implemented **k-means clustering** to organize data into distinct records, which I then exported for further use in the analytics layer.

```r
Lab8Data <- read.csv("City_Data.csv", header = T)
head(Lab8Data)
summary(Lab8Data)
str(Lab8Data)
cor(Lab8Data[, c(2:6)])
CityCluster <- kmeans(Lab8Data[, 2:6], 3, nstar = 100)
CityCluster
table(CityCluster$cluster, Lab8Data$Metropolitan_Area)
data.frame(CityCluster$size, CityCluster$center)
CityRecords <- data.frame(CityCluster$cluster, Lab8Data[c(1:6)])
head(CityRecords)
write.csv(CityRecords, file = "CityRecords.csv")
```

### Consulted Sources: External Sources Utilized
To achieve proficiency and resolve technical hurdles, I consulted several key resources:
* **Academic Guided Labs:** I utilized the **CIDM 6350** curriculum to understand Database Management Systems (DBMS) and the **CIDM 6355** labs to master Data Mining techniques.
* **Technical Documentation:** I relied on R documentation for functions such as `read.csv()`, `summary()`, and `kmeans()` to perform exploratory data analysis and statistical management.
* **Community Forums:** Similar to my analytics work, I frequently consult search engines and chat forums (like Stack Overflow) to troubleshoot syntax errors in SQL or R scripting.

### Summary Statement
My professional identity is bolstered by the ability to act as the "librarian" of an organization's information. Through my graduate studies, I have developed the propensity to take disorganized, "messy" data—whether it be raw SQL tables or CSV files—and transform it into a structured, relational model. In my future career, I plan to leverage these capabilities to ensure that my analytics are built on a foundation of "clean" data, allowing me to provide the strategic roadmaps necessary for operational optimization without the risk of "garbage in, garbage out."

### Capstone Preparedness
Regarding the Capstone prototype project, my proficiency in Data Management makes the "Structure" element of the project robust. I have the technical agility to serve as my own Data Architect, ensuring that the back-end database is correctly normalized and that the ETL processes I've practiced—such as clustering data in R or querying in SQL—are ready to feed into the final dashboard interface.

---

## Section 3: Contribution Towards the Capstone

### Why Data Management is Integratable
Data Management serves as the "**Skeleton**" of the IT organism. It provides the rigid, reliable frame that holds the information generated by other pillars. While **Software Systems** act as the muscle performing the work and **Networking** acts as the nervous system moving the data, Data Management provides the structural memory. Without this layer, the insights from **Analytics** would be impossible because there would be no "single source of truth" to visualize.

### How Data Management is Integratable
The technical integration relies on the **Relational Model** and standard protocols. The "handshake" occurs when I use SQL to create the tables that store data gathered by Software. For example, in a CMMS security audit, the software tracks user actions, the network moves that log data, and Data Management organizes it into a queryable database. This organized "blob" is then extracted via tools like Power BI to tell a story through the analytics layer.

### How it Integrates with Prior Work
Before entering the MS CISBA program, my management of data was often manual, reactive, and localized in flat files like Excel. My coursework has allowed me to automate these connections, moving from simple storage to building complex ecosystems. I have shifted from just "finding data" to proactively managing it through schema design and integrity rules, ensuring my dashboards are more consistent and dynamic than was previously possible in my role.

### The "Big Picture" Statement
The amalgamation of these four areas results in a living, breathing organism. In this model, **Data Management** provides the structural memory for storing data ("the skeleton"), giving the organism a frame to hold its information. When combined with the vision provided by **Analytics**, the muscle of **Software**, and the nervous system of **Networking**, I am able to move beyond reactive reporting into providing the strategic roadmaps necessary for operational success.
