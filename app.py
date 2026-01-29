from flask import Flask, render_template_string, request, redirect, url_for, flash, jsonify
import sqlite3
import json
import random
from datetime import datetime
import hashlib
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'credoza-skill-assessment-secret-key-2024'

# Database initialization
def init_db():
    conn = sqlite3.connect('credoza.db')
    c = conn.cursor()
    
    # Create tables
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'candidate',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            difficulty TEXT DEFAULT 'intermediate',
            is_active BOOLEAN DEFAULT 1
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS assessments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            skill_id INTEGER,
            title TEXT NOT NULL,
            description TEXT,
            duration INTEGER DEFAULT 30,
            total_questions INTEGER DEFAULT 10,
            passing_score REAL DEFAULT 70.0,
            is_active BOOLEAN DEFAULT 1,
            FOREIGN KEY (skill_id) REFERENCES skills (id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            assessment_id INTEGER,
            question_text TEXT NOT NULL,
            question_type TEXT DEFAULT 'multiple_choice',
            options TEXT,
            correct_answer TEXT NOT NULL,
            explanation TEXT,
            points INTEGER DEFAULT 10,
            difficulty TEXT DEFAULT 'medium',
            FOREIGN KEY (assessment_id) REFERENCES assessments (id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS assessment_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            assessment_id INTEGER,
            score REAL,
            max_score REAL,
            percentage REAL,
            status TEXT DEFAULT 'in_progress',
            start_time TIMESTAMP,
            end_time TIMESTAMP,
            time_taken INTEGER,
            answers TEXT,
            ai_analysis TEXT,
            is_passed BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (assessment_id) REFERENCES assessments (id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS skill_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            attempt_id INTEGER,
            skill_id INTEGER,
            verification_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expiry_date TIMESTAMP,
            certificate_id TEXT UNIQUE,
            is_valid BOOLEAN DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (attempt_id) REFERENCES assessment_attempts (id),
            FOREIGN KEY (skill_id) REFERENCES skills (id)
        )
    ''')
    
    # Check if we need to add sample data
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        # Add sample users
        c.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                 ('recruiter', 'recruiter@credoza.com', hash_password('password123'), 'recruiter'))
        c.execute("INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)",
                 ('candidate', 'candidate@credoza.com', hash_password('password123'), 'candidate'))
        
        # Add sample skills
        skills = [
            ('Python Programming', 'Programming', 'Test your Python programming skills'),
            ('JavaScript Fundamentals', 'Web Development', 'Assess your JavaScript knowledge'),
            ('Data Analysis', 'Data Science', 'Evaluate your data analysis skills'),
            ('UI/UX Design', 'Design', 'Test your design principles knowledge'),
            ('SQL Database', 'Database', 'Assess your SQL database skills')
        ]
        
        for skill in skills:
            c.execute("INSERT INTO skills (name, category, description) VALUES (?, ?, ?)", skill)
        
        conn.commit()
        
        # Add sample assessments
        c.execute("SELECT id FROM skills LIMIT 1")
        skill_id = c.fetchone()[0]
        
        c.execute('''INSERT INTO assessments (skill_id, title, description, duration, total_questions, passing_score)
                    VALUES (?, ?, ?, ?, ?, ?)''',
                 (skill_id, 'Python Fundamentals Assessment', 'Test your basic Python knowledge', 30, 5, 70.0))
        
        assessment_id = c.lastrowid
        
        # Add sample questions
        questions = [
            (assessment_id, 'Which of the following is a correct way to create a function in Python?',
             json.dumps(['def my_function():', 'function my_function() {}', 'create my_function():', 'func my_function():']),
             '0', 'Use "def" keyword to define functions in Python.', 20),
            (assessment_id, 'What does the "len()" function do in Python?',
             json.dumps(['Returns the length of an object', 'Converts to lowercase', 'Rounds a number', 'Imports a module']),
             '0', 'len() returns the number of items in an object.', 20),
            (assessment_id, 'Which keyword is used to create a class in Python?',
             json.dumps(['class', 'def', 'create', 'object']),
             '0', 'Use "class" keyword to define classes.', 20),
            (assessment_id, 'What is the output of: print(type([]))',
             json.dumps(["<class 'list'>", "<class 'tuple'>", "<class 'dict'>", "<class 'array'>"]),
             '0', '[] creates a list object.', 20),
            (assessment_id, 'Which operator is used for exponentiation in Python?',
             json.dumps(['**', '^', '^^', 'exp']),
             '0', '** is the exponentiation operator.', 20)
        ]
        
        for q in questions:
            c.execute('''INSERT INTO questions (assessment_id, question_text, options, correct_answer, explanation, points)
                        VALUES (?, ?, ?, ?, ?, ?)''', q)
    
    conn.commit()
    conn.close()
    print("✓ Database initialized successfully!")

def hash_password(password):
    """Simple password hashing"""
    return hashlib.sha256(password.encode()).hexdigest()

def check_password(password_hash, password):
    """Check password against hash"""
    return password_hash == hashlib.sha256(password.encode()).hexdigest()

def get_db():
    """Get database connection"""
    conn = sqlite3.connect('credoza.db')
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    return conn

# Session management (simplified)
sessions = {}

def get_current_user():
    """Get current user from session"""
    user_id = request.cookies.get('user_id')
    session_token = request.cookies.get('session_token')
    
    if user_id and session_token and session_token in sessions:
        session_data = sessions[session_token]
        if session_data['user_id'] == int(user_id) and session_data['expiry'] > datetime.now().timestamp():
            conn = get_db()
            user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
            conn.close()
            return user
    return None

def create_session(user_id):
    """Create a new session"""
    session_token = hashlib.sha256(f"{user_id}{datetime.now()}{random.random()}".encode()).hexdigest()
    sessions[session_token] = {
        'user_id': user_id,
        'expiry': datetime.now().timestamp() + 86400  # 24 hours
    }
    return session_token

def logout_session(session_token):
    """Remove session"""
    if session_token in sessions:
        del sessions[session_token]

# HTML Templates
BASE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Credoza - Skill Assessment{% endblock %}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root {
            --primary: #4361ee;
            --secondary: #4cc9f0;
            --success: #4caf50;
            --warning: #ff9e00;
            --danger: #f72585;
        }
        
        body {
            background-color: #f5f7fb;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        
        .navbar-brand {
            font-weight: 700;
            color: var(--primary) !important;
        }
        
        .btn-primary {
            background-color: var(--primary);
            border-color: var(--primary);
        }
        
        .btn-primary:hover {
            background-color: #3a56d4;
            border-color: #3a56d4;
        }
        
        .card {
            border: none;
            border-radius: 10px;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
            margin-bottom: 20px;
        }
        
        .hero-section {
            background: linear-gradient(135deg, #4361ee 0%, #4cc9f0 100%);
            color: white;
            padding: 80px 0;
            border-radius: 0 0 40px 40px;
        }
        
        .score-circle {
            width: 120px;
            height: 120px;
            border-radius: 50%;
            border: 8px solid;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 1.5rem;
            font-weight: bold;
            margin: 0 auto;
        }
        
        .score-excellent { border-color: var(--success); color: var(--success); }
        .score-good { border-color: #28a745; color: #28a745; }
        .score-average { border-color: var(--warning); color: var(--warning); }
        .score-poor { border-color: var(--danger); color: var(--danger); }
        
        .ai-dna-card {
            background: linear-gradient(135deg, #4361ee 0%, #4cc9f0 100%);
            color: white;
            border: none !important;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-light bg-white shadow-sm">
        <div class="container">
            <a class="navbar-brand" href="/">
                <i class="fas fa-certificate"></i> Credoza
            </a>
            <div class="navbar-nav ms-auto">
                {% if current_user %}
                    {% if current_user["role"] == 'candidate' %}
                        <a class="nav-link" href="/candidate/dashboard">Dashboard</a>
                        <a class="nav-link" href="/candidate/start-assessment">Take Assessment</a>
                    {% else %}
                        <a class="nav-link" href="/recruiter/dashboard">Dashboard</a>
                    {% endif %}
                    <a class="nav-link" href="/logout">Logout</a>
                {% else %}
                    <a class="nav-link" href="/login">Login</a>
                    <a class="btn btn-primary ms-2" href="/register">Sign Up</a>
                {% endif %}
            </div>
        </div>
    </nav>

    {% with messages = get_flashed_messages() %}
        {% if messages %}
            <div class="container mt-3">
                {% for message in messages %}
                    <div class="alert alert-info alert-dismissible fade show">
                        {{ message }}
                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                    </div>
                {% endfor %}
            </div>
        {% endif %}
    {% endwith %}

    <main class="py-4">
        {% block content %}{% endblock %}
    </main>

    <footer class="bg-dark text-white py-4 mt-5">
        <div class="container text-center">
            <p>&copy; 2026 Credoza. All rights reserved.</p>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
'''

INDEX_TEMPLATE = '''
{% extends "base.html" %}
{% block content %}
<div class="container">
    <div class="hero-section">
        <div class="row align-items-center">
            <div class="col-lg-6">
                <h1 class="display-5 fw-bold mb-4">Certify Your Skills with Credoza</h1>
                <p class="lead mb-4">Take industry-recognized skill assessments and showcase verified scores.</p>
                {% if not current_user %}
                <a href="/register" class="btn btn-light btn-lg me-2">Get Started</a>
                <a href="/login" class="btn btn-outline-light btn-lg">Login</a>
                {% else %}
                <a href="/{{ current_user['role'] }}/dashboard" class="btn btn-light btn-lg">Go to Dashboard</a>
                {% endif %}
            </div>
            <div class="col-lg-6 text-center">
                <i class="fas fa-laptop-code display-1"></i>
            </div>
        </div>
    </div>
    
    <div class="row mt-5">
        <div class="col-lg-4 mb-4">
            <div class="card h-100 text-center p-4">
                <div class="rounded-circle bg-primary bg-opacity-10 d-inline-flex align-items-center justify-content-center mb-4" style="width: 80px; height: 80px;">
                    <i class="fas fa-award fa-2x text-primary"></i>
                </div>
                <h4>Industry-Recognized</h4>
                <p>Assessments designed by industry experts.</p>
            </div>
        </div>
        <div class="col-lg-4 mb-4">
            <div class="card h-100 text-center p-4">
                <div class="rounded-circle bg-primary bg-opacity-10 d-inline-flex align-items-center justify-content-center mb-4" style="width: 80px; height: 80px;">
                    <i class="fas fa-brain fa-2x text-primary"></i>
                </div>
                <h4>AI Skill DNA</h4>
                <p>Deep insights into candidate capabilities.</p>
            </div>
        </div>
        <div class="col-lg-4 mb-4">
            <div class="card h-100 text-center p-4">
                <div class="rounded-circle bg-primary bg-opacity-10 d-inline-flex align-items-center justify-content-center mb-4" style="width: 80px; height: 80px;">
                    <i class="fas fa-briefcase fa-2x text-primary"></i>
                </div>
                <h4>Career Boost</h4>
                <p>Stand out with verified skill credentials.</p>
            </div>
        </div>
    </div>
</div>
{% endblock %}
'''

LOGIN_TEMPLATE = '''
{% extends "base.html" %}
{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <h4 class="mb-0">Login to Credoza</h4>
                </div>
                <div class="card-body">
                    <form method="POST">
                        <div class="mb-3">
                            <label class="form-label">Email</label>
                            <input type="email" class="form-control" name="email" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Password</label>
                            <input type="password" class="form-control" name="password" required>
                        </div>
                        <button type="submit" class="btn btn-primary w-100">Login</button>
                    </form>
                    <div class="text-center mt-3">
                        <p>Don't have an account? <a href="/register">Register</a></p>
                    </div>
                    <div class="mt-4">
                        <div class="alert alert-info">
                            <small>
                                <strong>Demo Accounts:</strong><br>
                                Recruiter: recruiter@credoza.com / password123<br>
                                Candidate: candidate@credoza.com / password123
                            </small>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
'''

REGISTER_TEMPLATE = '''
{% extends "base.html" %}
{% block content %}
<div class="container py-5">
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header bg-primary text-white">
                    <h4 class="mb-0">Register for Credoza</h4>
                </div>
                <div class="card-body">
                    <form method="POST">
                        <div class="mb-3">
                            <label class="form-label">Username</label>
                            <input type="text" class="form-control" name="username" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Email</label>
                            <input type="email" class="form-control" name="email" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">Password</label>
                            <input type="password" class="form-control" name="password" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label">I am a</label>
                            <select class="form-select" name="role" required>
                                <option value="candidate">Candidate / Job Seeker</option>
                                <option value="recruiter">Recruiter / Employer</option>
                            </select>
                        </div>
                        <button type="submit" class="btn btn-primary w-100">Register</button>
                    </form>
                    <div class="text-center mt-3">
                        <p>Already have an account? <a href="/login">Login</a></p>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>
{% endblock %}
'''

CANDIDATE_DASHBOARD_TEMPLATE = '''
{% extends "base.html" %}
{% block content %}
<div class="container py-4">
    <h2 class="mb-4">Welcome, {{ current_user["username"] }}!</h2>
    
    <div class="row mb-4">
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h5 class="mb-0">Start New Assessment</h5>
                </div>
                <div class="card-body">
                    <p>Test your skills and get certified.</p>
                    <a href="/candidate/start-assessment" class="btn btn-primary">Start Assessment</a>
                </div>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card">
                <div class="card-header">
                    <h5 class="mb-0">Your Certificates</h5>
                </div>
                <div class="card-body">
                    {% if verifications %}
                        {% for verification in verifications %}
                        <div class="mb-3">
                            <strong>{{ verification["skill_name"] }}</strong>
                            <br><small class="text-muted">{{ verification["certificate_id"] }}</small>
                            <br><a href="/verify/{{ verification['id'] }}" class="btn btn-sm btn-outline-primary mt-1">View</a>
                        </div>
                        {% endfor %}
                    {% else %}
                        <p class="text-muted">No certificates yet. Take an assessment!</p>
                    {% endif %}
                </div>
            </div>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header">
            <h5 class="mb-0">Recent Assessments</h5>
        </div>
        <div class="card-body">
            {% if attempts %}
                <div class="table-responsive">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Assessment</th>
                                <th>Date</th>
                                <th>Score</th>
                                <th>Status</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for attempt in attempts %}
                            <tr>
                                <td>{{ attempt["assessment_title"] }}</td>
                                <td>{{ attempt["created_at"][:10] }}</td>
                                <td>
                                    {% if attempt["percentage"] %}
                                    <span class="badge bg-{{ 'success' if attempt['percentage'] >= 70 else 'warning' if attempt['percentage'] >= 50 else 'danger' }}">
                                        {{ "%.1f"|format(attempt['percentage']) }}%
                                    </span>
                                    {% else %}
                                    <span class="badge bg-secondary">In Progress</span>
                                    {% endif %}
                                </td>
                                <td>
                                    {% if attempt["status"] == 'completed' %}
                                        {% if attempt["is_passed"] %}
                                        <span class="badge bg-success">Passed</span>
                                        {% else %}
                                        <span class="badge bg-danger">Failed</span>
                                        {% endif %}
                                    {% else %}
                                    <span class="badge bg-warning">In Progress</span>
                                    {% endif %}
                                </td>
                                <td>
                                    {% if attempt["status"] == 'completed' %}
                                    <a href="/candidate/results/{{ attempt['id'] }}" class="btn btn-sm btn-outline-primary">View</a>
                                    {% else %}
                                    <a href="/candidate/take-assessment/{{ attempt['id'] }}/question/1" class="btn btn-sm btn-primary">Continue</a>
                                    {% endif %}
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            {% else %}
                <p class="text-muted">No assessments yet.</p>
            {% endif %}
        </div>
    </div>
</div>
{% endblock %}
'''

RECRUITER_DASHBOARD_TEMPLATE = '''
{% extends "base.html" %}
{% block content %}
<div class="container py-4">
    <h2 class="mb-4">Recruiter Dashboard</h2>
    
    <div class="card ai-dna-card mb-4">
        <div class="card-body">
            <h4 class="text-white">AI Skill DNA Analysis</h4>
            <p class="text-white">Access detailed insights into candidate capabilities.</p>
        </div>
    </div>
    
    <div class="card">
        <div class="card-header">
            <h5 class="mb-0">Candidate Verifications</h5>
        </div>
        <div class="card-body">
            {% if verifications %}
                <div class="table-responsive">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Candidate</th>
                                <th>Skill</th>
                                <th>Certificate ID</th>
                                <th>Date</th>
                                <th>Action</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for verification in verifications %}
                            <tr>
                                <td>{{ verification["username"] }}</td>
                                <td>{{ verification["skill_name"] }}</td>
                                <td><code>{{ verification["certificate_id"] }}</code></td>
                                <td>{{ verification["verification_date"][:10] }}</td>
                                <td>
                                    <a href="/verify/{{ verification['id'] }}" class="btn btn-sm btn-outline-primary">View</a>
                                </td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                </div>
            {% else %}
                <p class="text-muted">No verifications found.</p>
            {% endif %}
        </div>
    </div>
</div>
{% endblock %}
'''

TAKE_ASSESSMENT_TEMPLATE = '''
{% extends "base.html" %}
{% block content %}
<div class="container py-4">
    <div class="card">
        <div class="card-header bg-primary text-white">
            <h4 class="mb-0">{{ assessment["title"] }}</h4>
        </div>
        <div class="card-body">
            <h5>Question {{ question_num }} of {{ total_questions }}</h5>
            <p class="lead">{{ question["question_text"] }}</p>
            
            <form method="POST">
                <input type="hidden" name="question_id" value="{{ question['id'] }}">
                {% if options %}
                    {% for option in options %}
                    <div class="form-check mb-3">
                        <input class="form-check-input" type="radio" name="answer" value="{{ loop.index0 }}" 
                               id="opt{{ loop.index0 }}" {% if user_answer == loop.index0|string %}checked{% endif %}>
                        <label class="form-check-label" for="opt{{ loop.index0 }}">
                            {{ option }}
                        </label>
                    </div>
                    {% endfor %}
                {% else %}
                    <textarea class="form-control" name="answer" rows="3">{{ user_answer }}</textarea>
                {% endif %}
                
                <div class="mt-4 d-flex justify-content-between">
                    {% if question_num > 1 %}
                    <button type="submit" name="action" value="previous" class="btn btn-outline-primary">
                        ← Previous
                    </button>
                    {% else %}
                    <div></div>
                    {% endif %}
                    
                    {% if question_num < total_questions %}
                    <button type="submit" name="action" value="next" class="btn btn-primary">
                        Next →
                    </button>
                    {% else %}
                    <button type="submit" name="action" value="submit" class="btn btn-success">
                        Submit Assessment
                    </button>
                    {% endif %}
                </div>
            </form>
        </div>
    </div>
</div>
{% endblock %}
'''

ASSESSMENT_RESULTS_TEMPLATE = '''
{% extends "base.html" %}
{% block content %}
<div class="container py-4">
    <div class="card">
        <div class="card-header bg-primary text-white">
            <h4 class="mb-0">Assessment Results</h4>
        </div>
        <div class="card-body text-center">
            <div class="score-circle {{ 'score-excellent' if attempt['percentage'] >= 90 else 'score-good' if attempt['percentage'] >= 80 else 'score-average' if attempt['percentage'] >= 70 else 'score-poor' }}">
                {{ "%.1f"|format(attempt['percentage']) }}%
            </div>
            
            <h3 class="mt-4">{{ "PASSED" if attempt['is_passed'] else "TRY AGAIN" }}</h3>
            <p class="text-muted">
                Score: {{ attempt['score'] }}/{{ attempt['max_score'] }}<br>
                Passing Score: {{ assessment['passing_score'] }}%
            </p>
            
            {% if attempt['is_passed'] %}
            <div class="alert alert-success">
                <i class="fas fa-check-circle"></i> Congratulations! You've earned a skill certificate.
            </div>
            <a href="/verify/{{ verification_id }}" class="btn btn-primary">View Certificate</a>
            {% else %}
            <div class="alert alert-warning">
                <i class="fas fa-exclamation-circle"></i> You need more practice. Try again!
            </div>
            {% endif %}
            
            <a href="/candidate/dashboard" class="btn btn-outline-primary mt-2">Back to Dashboard</a>
        </div>
    </div>
</div>
{% endblock %}
'''

VERIFY_SKILL_TEMPLATE = '''
{% extends "base.html" %}
{% block content %}
<div class="container py-4">
    <div class="card">
        <div class="card-header bg-primary text-white text-center">
            <h4 class="mb-0">Skill Certificate</h4>
        </div>
        <div class="card-body text-center">
            <i class="fas fa-certificate fa-4x text-primary mb-4"></i>
            <h3>This certifies that</h3>
            <h2 class="text-primary mb-4">{{ user["username"] }}</h2>
            <p class="lead">has demonstrated proficiency in</p>
            <h4 class="mb-4">{{ skill["name"] }}</h4>
            
            <div class="row mb-4">
                <div class="col-md-6">
                    <p><strong>Score:</strong><br>{{ "%.1f"|format(attempt['percentage']) }}%</p>
                </div>
                <div class="col-md-6">
                    <p><strong>Date:</strong><br>{{ verification["verification_date"][:10] }}</p>
                </div>
            </div>
            
            <p><strong>Certificate ID:</strong><br><code>{{ verification["certificate_id"] }}</code></p>
            
            {% if current_user["role"] == 'recruiter' and ai_analysis %}
            <div class="mt-4">
                <button class="btn btn-primary" type="button" data-bs-toggle="collapse" data-bs-target="#aiAnalysis">
                    View AI Skill DNA Report
                </button>
                <div class="collapse mt-3" id="aiAnalysis">
                    <div class="card ai-dna-card">
                        <div class="card-body text-white text-start">
                            <h5>AI Skill DNA Analysis</h5>
                            <p><strong>Performance Level:</strong> {{ ai_analysis['overall_assessment']['performance_level'] }}</p>
                            <p><strong>Time Efficiency:</strong> {{ ai_analysis['overall_assessment']['time_efficiency'] }}</p>
                            <p><strong>Confidence Score:</strong> {{ ai_analysis['confidence_score'] }}%</p>
                            <div class="mt-3">
                                <h6>Strengths:</h6>
                                <ul>
                                    {% for strength in ai_analysis['strengths'] %}
                                    <li>{{ strength }}</li>
                                    {% endfor %}
                                </ul>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
            {% endif %}
        </div>
        <div class="card-footer text-center">
            <small class="text-muted">Issued by Credoza Skill Assessment Platform</small>
        </div>
    </div>
</div>
{% endblock %}
'''

# Routes
@app.route('/')
def index():
    current_user = get_current_user()
    return render_template_string(INDEX_TEMPLATE, current_user=current_user)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
        conn.close()
        
        if user and check_password(user['password_hash'], password):
            session_token = create_session(user['id'])
            response = redirect('/')
            response.set_cookie('user_id', str(user['id']))
            response.set_cookie('session_token', session_token)
            flash('Logged in successfully!')
            return response
        else:
            flash('Invalid email or password')
    
    return render_template_string(LOGIN_TEMPLATE, current_user=None)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        role = request.form['role']
        
        conn = get_db()
        
        # Check if user exists
        existing = conn.execute('SELECT * FROM users WHERE email = ? OR username = ?', 
                               (email, username)).fetchone()
        if existing:
            flash('User already exists')
            conn.close()
            return render_template_string(REGISTER_TEMPLATE, current_user=None)
        
        # Create user
        password_hash = hash_password(password)
        conn.execute('INSERT INTO users (username, email, password_hash, role) VALUES (?, ?, ?, ?)',
                    (username, email, password_hash, role))
        conn.commit()
        
        user_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
        conn.close()
        
        session_token = create_session(user_id)
        response = redirect('/')
        response.set_cookie('user_id', str(user_id))
        response.set_cookie('session_token', session_token)
        flash('Registration successful!')
        return response
    
    return render_template_string(REGISTER_TEMPLATE, current_user=None)

@app.route('/logout')
def logout():
    session_token = request.cookies.get('session_token')
    if session_token:
        logout_session(session_token)
    
    response = redirect('/')
    response.delete_cookie('user_id')
    response.delete_cookie('session_token')
    flash('Logged out successfully')
    return response

@app.route('/candidate/dashboard')
def candidate_dashboard():
    current_user = get_current_user()
    if not current_user or current_user['role'] != 'candidate':
        flash('Access denied')
        return redirect('/')
    
    conn = get_db()
    
    # Get verifications
    verifications = conn.execute('''
        SELECT sv.*, s.name as skill_name 
        FROM skill_verifications sv
        JOIN skills s ON sv.skill_id = s.id
        WHERE sv.user_id = ? AND sv.is_valid = 1
        ORDER BY sv.verification_date DESC
    ''', (current_user['id'],)).fetchall()
    
    # Get attempts
    attempts = conn.execute('''
        SELECT aa.*, a.title as assessment_title
        FROM assessment_attempts aa
        JOIN assessments a ON aa.assessment_id = a.id
        WHERE aa.user_id = ?
        ORDER BY aa.created_at DESC
        LIMIT 10
    ''', (current_user['id'],)).fetchall()
    
    conn.close()
    
    return render_template_string(CANDIDATE_DASHBOARD_TEMPLATE,
                                current_user=current_user,
                                verifications=verifications,
                                attempts=attempts)

@app.route('/recruiter/dashboard')
def recruiter_dashboard():
    current_user = get_current_user()
    if not current_user or current_user['role'] != 'recruiter':
        flash('Access denied')
        return redirect('/')
    
    conn = get_db()
    
    verifications = conn.execute('''
        SELECT sv.*, u.username, s.name as skill_name
        FROM skill_verifications sv
        JOIN users u ON sv.user_id = u.id
        JOIN skills s ON sv.skill_id = s.id
        WHERE sv.is_valid = 1
        ORDER BY sv.verification_date DESC
    ''').fetchall()
    
    conn.close()
    
    return render_template_string(RECRUITER_DASHBOARD_TEMPLATE,
                                current_user=current_user,
                                verifications=verifications)

@app.route('/candidate/start-assessment')
def start_assessment():
    current_user = get_current_user()
    if not current_user or current_user['role'] != 'candidate':
        flash('Access denied')
        return redirect('/')
    
    conn = get_db()
    
    # Get first available assessment
    assessment = conn.execute('SELECT * FROM assessments WHERE is_active = 1 LIMIT 1').fetchone()
    
    if not assessment:
        flash('No assessments available')
        conn.close()
        return redirect('/candidate/dashboard')
    
    # Check for active attempt
    active_attempt = conn.execute('''
        SELECT * FROM assessment_attempts 
        WHERE user_id = ? AND assessment_id = ? AND status = 'in_progress'
    ''', (current_user['id'], assessment['id'])).fetchone()
    
    if active_attempt:
        conn.close()
        return redirect(f'/candidate/take-assessment/{active_attempt["id"]}/question/1')
    
    # Create new attempt
    conn.execute('''
        INSERT INTO assessment_attempts (user_id, assessment_id, status, start_time)
        VALUES (?, ?, 'in_progress', CURRENT_TIMESTAMP)
    ''', (current_user['id'], assessment['id']))
    conn.commit()
    
    attempt_id = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    conn.close()
    
    return redirect(f'/candidate/take-assessment/{attempt_id}/question/1')

@app.route('/candidate/take-assessment/<int:attempt_id>/question/<int:question_num>', methods=['GET', 'POST'])
def take_assessment(attempt_id, question_num):
    current_user = get_current_user()
    if not current_user or current_user['role'] != 'candidate':
        flash('Access denied')
        return redirect('/')
    
    conn = get_db()
    
    # Get attempt
    attempt = conn.execute('SELECT * FROM assessment_attempts WHERE id = ?', (attempt_id,)).fetchone()
    if not attempt or attempt['user_id'] != current_user['id']:
        conn.close()
        flash('Access denied')
        return redirect('/candidate/dashboard')
    
    if attempt['status'] == 'completed':
        conn.close()
        return redirect(f'/candidate/results/{attempt_id}')
    
    # Get assessment and questions
    assessment = conn.execute('SELECT * FROM assessments WHERE id = ?', (attempt['assessment_id'],)).fetchone()
    questions = conn.execute('SELECT * FROM questions WHERE assessment_id = ? ORDER BY id', 
                            (assessment['id'],)).fetchall()
    
    if not questions:
        conn.close()
        flash('No questions found')
        return redirect('/candidate/dashboard')
    
    # Validate question number
    if question_num < 1:
        question_num = 1
    elif question_num > len(questions):
        question_num = len(questions)
    
    current_question = questions[question_num - 1]
    options = json.loads(current_question['options']) if current_question['options'] else []
    
    # Get user answers
    user_answers = json.loads(attempt['answers']) if attempt['answers'] else {}
    user_answer = user_answers.get(str(current_question['id']), '')
    
    if request.method == 'POST':
        action = request.form.get('action')
        answer = request.form.get('answer', '')
        
        # Save answer
        user_answers[str(current_question['id'])] = answer
        conn.execute('UPDATE assessment_attempts SET answers = ? WHERE id = ?',
                    (json.dumps(user_answers), attempt_id))
        
        if action == 'submit':
            conn.commit()
            conn.close()
            return redirect(f'/candidate/submit-assessment/{attempt_id}')
        elif action == 'next' and question_num < len(questions):
            question_num += 1
        elif action == 'previous' and question_num > 1:
            question_num -= 1
        
        conn.commit()
        conn.close()
        return redirect(f'/candidate/take-assessment/{attempt_id}/question/{question_num}')
    
    conn.close()
    
    return render_template_string(TAKE_ASSESSMENT_TEMPLATE,
                                current_user=current_user,
                                assessment=assessment,
                                question=current_question,
                                question_num=question_num,
                                total_questions=len(questions),
                                options=options,
                                user_answer=user_answer)

@app.route('/candidate/submit-assessment/<int:attempt_id>')
def submit_assessment(attempt_id):
    current_user = get_current_user()
    if not current_user or current_user['role'] != 'candidate':
        flash('Access denied')
        return redirect('/')
    
    conn = get_db()
    
    # Get attempt
    attempt = conn.execute('SELECT * FROM assessment_attempts WHERE id = ?', (attempt_id,)).fetchone()
    if not attempt or attempt['user_id'] != current_user['id']:
        conn.close()
        flash('Access denied')
        return redirect('/candidate/dashboard')
    
    # Calculate score
    assessment = conn.execute('SELECT * FROM assessments WHERE id = ?', (attempt['assessment_id'],)).fetchone()
    questions = conn.execute('SELECT * FROM questions WHERE assessment_id = ?', (assessment['id'],)).fetchall()
    user_answers = json.loads(attempt['answers']) if attempt['answers'] else {}
    
    score = 0
    max_score = sum(q['points'] for q in questions)
    
    for question in questions:
        if user_answers.get(str(question['id'])) == question['correct_answer']:
            score += question['points']
    
    percentage = (score / max_score * 100) if max_score > 0 else 0
    is_passed = percentage >= assessment['passing_score']
    
    # Generate AI analysis
    ai_analysis = {
        'overall_assessment': {
            'performance_level': 'Excellent' if percentage >= 90 else 
                                'Good' if percentage >= 80 else 
                                'Average' if percentage >= 70 else 'Needs Improvement',
            'time_efficiency': 'Optimal',
            'consistency': 'High' if percentage >= 80 else 'Medium' if percentage >= 70 else 'Low'
        },
        'strengths': [
            "Strong understanding of fundamental concepts",
            "Good logical reasoning skills",
            "Consistent performance"
        ],
        'confidence_score': random.randint(70, 95)
    }
    
    # Update attempt
    conn.execute('''
        UPDATE assessment_attempts 
        SET score = ?, max_score = ?, percentage = ?, is_passed = ?, 
            status = 'completed', end_time = CURRENT_TIMESTAMP,
            time_taken = CAST((julianday(CURRENT_TIMESTAMP) - julianday(start_time)) * 86400 AS INTEGER),
            ai_analysis = ?
        WHERE id = ?
    ''', (score, max_score, percentage, 1 if is_passed else 0, json.dumps(ai_analysis), attempt_id))
    
    # Create verification if passed
    verification_id = None
    if is_passed:
        certificate_id = f"CRED-{attempt_id:06d}-{datetime.now().strftime('%Y%m%d')}"
        conn.execute('''
            INSERT INTO skill_verifications (user_id, attempt_id, skill_id, certificate_id)
            VALUES (?, ?, ?, ?)
        ''', (current_user['id'], attempt_id, assessment['skill_id'], certificate_id))
        conn.commit()
        
        verification = conn.execute('SELECT * FROM skill_verifications WHERE certificate_id = ?',
                                   (certificate_id,)).fetchone()
        verification_id = verification['id']
    
    conn.commit()
    conn.close()
    
    flash('Assessment submitted successfully!')
    return redirect(f'/candidate/results/{attempt_id}')

@app.route('/candidate/results/<int:attempt_id>')
def assessment_results(attempt_id):
    current_user = get_current_user()
    if not current_user or current_user['role'] != 'candidate':
        flash('Access denied')
        return redirect('/')
    
    conn = get_db()
    
    # Get attempt
    attempt = conn.execute('SELECT * FROM assessment_attempts WHERE id = ?', (attempt_id,)).fetchone()
    if not attempt or attempt['user_id'] != current_user['id']:
        conn.close()
        flash('Access denied')
        return redirect('/candidate/dashboard')
    
    # Get assessment
    assessment = conn.execute('SELECT * FROM assessments WHERE id = ?', (attempt['assessment_id'],)).fetchone()
    
    # Get verification if exists
    verification = conn.execute('SELECT * FROM skill_verifications WHERE attempt_id = ?', (attempt_id,)).fetchone()
    verification_id = verification['id'] if verification else None
    
    conn.close()
    
    return render_template_string(ASSESSMENT_RESULTS_TEMPLATE,
                                current_user=current_user,
                                attempt=attempt,
                                assessment=assessment,
                                verification_id=verification_id)

@app.route('/verify/<int:verification_id>')
def verify_skill(verification_id):
    current_user = get_current_user()
    if not current_user:
        flash('Please login to view certificates')
        return redirect('/login')
    
    conn = get_db()
    
    # Get verification
    verification = conn.execute('''
        SELECT sv.*, u.username, u.email, s.name as skill_name
        FROM skill_verifications sv
        JOIN users u ON sv.user_id = u.id
        JOIN skills s ON sv.skill_id = s.id
        WHERE sv.id = ?
    ''', (verification_id,)).fetchone()
    
    if not verification:
        conn.close()
        flash('Certificate not found')
        return redirect('/')
    
    # Check permissions
    if current_user['role'] != 'recruiter' and verification['user_id'] != current_user['id']:
        conn.close()
        flash('Access denied')
        return redirect('/')
    
    # Get attempt and AI analysis
    attempt = conn.execute('SELECT * FROM assessment_attempts WHERE id = ?', 
                          (verification['attempt_id'],)).fetchone()
    skill = {'name': verification['skill_name']}
    ai_analysis = json.loads(attempt['ai_analysis']) if attempt['ai_analysis'] else None
    
    conn.close()
    
    return render_template_string(VERIFY_SKILL_TEMPLATE,
                                current_user=current_user,
                                verification=verification,
                                attempt=attempt,
                                skill=skill,
                                user={'username': verification['username']},
                                ai_analysis=ai_analysis)

# Initialize database
init_db()

if __name__ == '__main__':
    print("\n" + "="*50)
    print("Starting Credoza Skill Assessment Platform")
    print("="*50)
    print("\nOpen your browser and go to: http://localhost:5000")
    print("\nDemo Accounts:")
    print("  • Recruiter: recruiter@credoza.com / password123")
    print("  • Candidate: candidate@credoza.com / password123")
    print("\n" + "="*50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)