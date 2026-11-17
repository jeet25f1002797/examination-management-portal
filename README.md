EXAMINATION MANAGEMENT PORTAL
Modern Application Development I (MAD-I) – Project Report
Student Name: Jeet Bhakat     Roll Number: 25F1002797
Programme: BS Degree in Data Science and Applications
Institution: Indian Institute of Technology Madras
Course: Modern Application Development I (MAD-I)
Project Title: Examination Management Portal
1. Project Details
1.1 Problem Statement
The objective of this project is to develop a web-based Examination Management Portal that simplifies and manages the
examination process for administrators, examiners and students. Traditional examination management often involves manual
handling of examination schedules, examiner assignments, student registrations, slot bookings and result management. This
can lead to scheduling conflicts, booking errors and difficulties in maintaining examination records.
The proposed system provides a centralized platform where administrators can manage courses and examinations, assign
examiners, control examination schedules and booking periods, while examiners can create examination slots and evaluate
students. Students can view available examination slots, book examinations and access their results and feedback.
1.2 Approach and Implementation
The application was developed using Python Flask for backend development, SQLite for database management and HTML,
CSS, Bootstrap and Jinja2 for the user interface. It follows a role-based architecture with three user roles: administrator,
examiner and student.
Administrator
• Accesses the system through a predefined administrator account.
• Manages courses and examinations; approves pending examiner registrations and activates or deactivates approved examiners.
• Assigns examinations to examiners, manages rubrics and controls slot creation and student booking periods.
• Sets examination dates, times and booking deadlines, and views students, examiners, slots and booking records.
Examiner
• Registers and logs in; requires administrator approval before accessing the dashboard.
• Views assigned examinations and creates slots with date, time and available capacity.
• Views students registered for their slots and evaluates students by submitting marks and feedback.
• Can manage only the examination slots and students associated with their assignments.
Student
• Registers and logs in; views available examinations, slots, examiners, dates, times and available seats.
• Books an available slot and can cancel an active booking subject to applicable rules.
• Views booking history, examination status, published marks and examiner feedback.
1.3 Important System Features
• Role-based authentication and authorization, with password hashing.
• Administrator-controlled examiner approval and examination assignments.
• Course, examination and rubric management.
• Examination slot creation with capacity restrictions.
• Administrator-controlled slot creation and student booking, including booking deadlines.
• Prevention of duplicate and over-capacity bookings.
• Examination evaluation with marks and feedback; separate dashboards for all three roles.



2. Frameworks and Libraries Used
Technology Purpose
Python Main programming language
Flask Backend web framework and routing
SQLite3 Relational database management
HTML5 / CSS3 Webpage structure, styling and layout
Bootstrap Responsive user interface
Jinja2 Dynamic HTML templates
Werkzeug Security Password hashing and verification
Python datetime Examination date and time validation
functools.wraps Custom login and role-based access decorators
Architecture: Flask-based server-side web application using SQLite and Jinja2 templates. SQLAlchemy ORM was not used;
database operations were performed using Python's built-in sqlite3 library and SQL queries.
3. Database Design and ER Diagram
The application uses SQLite as its relational database. The current project description identifies the following nine tables:
Table Purpose
users Stores administrator, examiner and student accounts
courses Stores course codes and course names
exams Stores examination information and scheduling details
examiner_assignments Maintains examination assignments to examiners
rubrics Stores examination evaluation criteria
slots Stores examination slots, examiners and capacity
bookings Stores student examination bookings and booking status
results Stores marks and examiner feedback
system_settings Stores global controls for slot creation and student booking
3.1 Table Relationships
• Users – Examiner Assignments: one examiner can have multiple examination assignments.
• Exams – Examiner Assignments: one examination can be assigned to multiple examiners.
• Courses – Exams: one course can have multiple examinations.
• Exams – Rubrics: one examination can have multiple evaluation criteria.
• Exams – Slots: one examination can have multiple examination slots.
• Users – Slots: one examiner can create multiple examination slots.
• Users – Bookings: one student can have multiple booking records over time.
• Slots – Bookings: one slot can have multiple student bookings, subject to capacity.
• Bookings – Results: each booking can have one associated evaluation result.
   
3.2 ER Diagram (Conceptual)
USERS
(Admin / Examiner / Student)
n
nnn EXAMINER_ASSIGNMENTS nn EXAMS nn COURSES
n nnn RUBRICS
n nnn SLOTS nn USERS (Examiner)
nnn BOOKINGS nn SLOTS
n
nnn RESULTS
SYSTEM_SETTINGS (global slot-creation and booking controls)
The database uses primary keys and foreign keys to maintain relationships and data integrity. Unique constraints are used to
prevent duplicate records in important operations.
4. Application Routes and API Endpoints
The application primarily uses Flask server-side routes to process requests and render HTML templates. It does not currently
implement a separate REST API for the main application resources.
4.1 Authentication Routes
Method Endpoint Description
GET / Redirects to login or dashboard
GET, POST /register User registration
GET, POST /login User authentication
GET /logout Logs out the current user
GET /dashboard Displays the role-specific dashboard
4.2 Administrator Routes
Method Endpoint Description
POST /course Add a course
GET, POST /course//edit Edit course details
POST /course//delete Delete a course
POST /exam Add an examination
GET, POST /exam//edit Edit examination and rubric details
POST /exam//delete Delete an examination
POST /approve/ Approve an examiner
POST /activate/ Activate an examiner
POST /deactivate/ Deactivate an examiner
POST /admin/assign-examiner Assign an examination to an examiner
POST /admin/remove-assignment/ Remove an examiner assignment
POST /admin/exam//booking-window Set examination booking deadlines
POST /admin/toggle-slot-creation Control examiner slot creation
POST /admin/toggle-student-booking Control student booking
GET /admin/examiners View examiners
GET /admin/students View students
GET /admin/slots View examination slots
GET /admin/bookings View booking records
4.3 Examiner and Student Routes
Role
Method
Endpoint
Description
Examiner
Examiner
GET, POST
GET
/slot/
/slot//students
Create an examination slot
View students booked in a slot
Examiner
Student
POST
POST
/evaluate/
/book/
Submit or update marks and feedback
Book an examination slot
Student
System
POST
GET
/cancel/
/health
Cancel an active booking
Return application health status as JSON
5. AI/LLM Usage Declaration
Generative AI (ChatGPT) was used as an assistance tool during the development of this project. The extent of AI assistance
included:
• Understanding Flask concepts, routing and request handling.
• Understanding SQLite database queries, joins, foreign keys and relationships.
• Assistance with debugging Python, Flask and SQL errors.
• Suggestions for implementing role-based authentication and access control.
• Assistance with improving HTML templates and Bootstrap-based dashboard layouts.
• Explanations of application logic and guidance on implementing examination management, examiner assignment, slot booking and
evaluation functionality.
The AI tool was used for learning, code explanations, debugging and implementation guidance. The project code was reviewed,
modified and integrated into the application during development by the student.
Declaration: I acknowledge the use of AI assistance and understand that I am responsible for explaining the submitted source
code, database design and application functionality.
6. Presentation Video
Project Demonstration Video (Google Drive):
[PASTE YOUR GOOGLE DRIVE VIDEO LINK HERE]
The presentation demonstrates the application's main functionalities, including administrator operations, examiner assignment
and slot management, student booking and examination evaluation.
7. Conclusion
The Examination Management Portal provides a centralized solution for managing the examination lifecycle. It simplifies
administrative operations, organizes examiner responsibilities and provides students with a convenient examination booking and
result-viewing system.
The project demonstrates the practical application of Python Flask, SQLite database management, server-side rendering,
authentication, role-based authorization and relational database design. Through this project, I gained practical experience in
backend development, database integration, SQL queries, application routing, debugging and building dynamic web
applications.

Examination Management Portal | MAD-I
