from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_file, make_response, g, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from db import get_db_connection
import datetime
from collections import defaultdict
import socket
import subprocess
import platform

app = Flask(__name__)
app.secret_key = 'SUPERSECRETKEY!@#$%^&*()-=0987654321)((*&&&&&&&&&&&&&&&&&------------------))'  # Change this to a secure random value
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1 GB

# Add max and min functions to Jinja2 environment
app.jinja_env.globals.update(max=max, min=min)

def get_local_ip():
    """Get the local IP address of the machine"""
    try:
        # Connect to a remote address to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "127.0.0.1"

def get_network_info():
    """Get comprehensive network information"""
    try:
        # Get local IP
        local_ip = get_local_ip()
        
        # Get hostname
        hostname = socket.gethostname()
        
        # Get all IP addresses
        all_ips = []
        try:
            for info in socket.getaddrinfo(hostname, None):
                ip = info[4][0]
                if ip not in all_ips and not ip.startswith('127.'):
                    all_ips.append(ip)
        except:
            pass
        
        return {
            'local_ip': local_ip,
            'hostname': hostname,
            'all_ips': all_ips,
            'port': 5000,
            'access_urls': [f"http://{ip}:5000" for ip in [local_ip] + all_ips if ip != local_ip]
        }
    except Exception as e:
        return {
            'local_ip': '127.0.0.1',
            'hostname': 'localhost',
            'all_ips': [],
            'port': 5000,
            'access_urls': [],
            'error': str(e)
        }

@app.before_request
def update_last_seen():
    if 'user_id' in session:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET last_seen = NOW() WHERE id = %s", (session['user_id'],))
        conn.commit()
        cursor.close()
        conn.close()

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()

        if user and check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['role'] = user['role']
            session['username'] = user['username']
            
            # Set flash message for successful login
            flash('Login successful! Welcome back.', 'success')
            
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user['role'] == 'receiving1':
                return redirect(url_for('receiving1_dashboard'))
            elif user['role'] == 'receiving2':
                return redirect(url_for('receiving2_dashboard'))
            elif user['role'] == 'docs':
                return redirect(url_for('docs_dashboard'))
            elif user['role'] == 'releasing':
                return redirect(url_for('releasing_dashboard'))
        else:
            flash('Invalid username or password. Please try again.', 'danger')
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login_alias():
    return login()

@app.route('/logout', methods=['POST'])
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/network_info')
def network_info():
    """Display network information for accessing the application"""
    network_info = get_network_info()
    return render_template('network_info.html', network_info=network_info)

@app.route('/api/network_info')
def api_network_info():
    """API endpoint to get network information"""
    return jsonify(get_network_info())

@app.route('/admin_dashboard')
def admin_dashboard():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS total_users FROM users")
    total_users = cursor.fetchone()['total_users']
    cursor.execute("SELECT COUNT(*) AS total_documents FROM receiving1_documents")
    total_documents = cursor.fetchone()['total_documents']
    cursor.execute("SELECT COUNT(*) AS total_daily_documents FROM receiving1_documents WHERE DATE(date_received) = CURDATE()")
    total_daily_documents = cursor.fetchone()['total_daily_documents']
    # Only fetch documents added today for the recent documents table - exclude document_blob
    cursor.execute("SELECT id, date_received, time_received, control_no, source, particulars, received_by, document_receiver, forwarded_to, document_file, created_at, routed_to_receiving2, accepted_by_receiving2 FROM receiving1_documents WHERE DATE(date_received) = CURDATE() ORDER BY created_at DESC LIMIT 5")
    recent_documents_admin = cursor.fetchall()
    cursor.execute("SELECT id, date_received, time_received, control_no, source, particulars, received_by, document_receiver, forwarded_to, document_file, created_at, routed_to_receiving2, accepted_by_receiving2 FROM receiving1_documents ORDER BY date_received DESC, time_received DESC, created_at DESC")
    all_receiving1_documents = cursor.fetchall()
    try:
        cursor.execute("SELECT COUNT(*) AS total_other FROM other_documents")
        total_other_documents = cursor.fetchone()['total_other']
    except:
        total_other_documents = 0
    try:
        cursor.execute("SELECT COUNT(*) AS total_gso FROM gso_documents")
        total_gso = cursor.fetchone()['total_gso']
    except:
        total_gso = 0
    try:
        cursor.execute("SELECT COUNT(*) AS total_travel FROM travel_documents")
        total_travel = cursor.fetchone()['total_travel']
    except:
        total_travel = 0
    # Add special permit and application leave totals
    try:
        cursor.execute("SELECT COUNT(*) AS total_special_permit FROM special_permit_documents")
        total_special_permit = cursor.fetchone()['total_special_permit']
    except:
        total_special_permit = 0
    try:
        cursor.execute("SELECT COUNT(*) AS total_application_leave FROM application_leave_documents")
        total_application_leave = cursor.fetchone()['total_application_leave']
    except:
        total_application_leave = 0
    try:
        cursor.execute("SELECT COUNT(*) AS total_outgoing_docs_receiving2 FROM receiving1_documents WHERE accepted_by_receiving2 = 1")
        total_outgoing_docs_receiving2 = cursor.fetchone()['total_outgoing_docs_receiving2']
    except:
        total_outgoing_docs_receiving2 = 0
    # Add total accepted count for outgoing docs
    try:
        cursor.execute("SELECT COUNT(*) AS total_accepted FROM accepted_documents")
        total_accepted_count = cursor.fetchone()['total_accepted']
    except:
        total_accepted_count = 0
    cursor.close()
    conn.close()
    return render_template('admin/admin_dashboard.html', total_users=total_users, total_documents=total_documents, total_daily_documents=total_daily_documents, recent_documents_admin=recent_documents_admin, all_receiving1_documents=all_receiving1_documents, total_other_documents=total_other_documents, total_gso=total_gso, total_travel=total_travel, total_special_permit=total_special_permit, total_application_leave=total_application_leave, total_outgoing_docs_receiving2=total_outgoing_docs_receiving2, total_accepted_count=total_accepted_count)

@app.route('/dashboard/receiving1')
def receiving1_dashboard():
    if session.get('role') not in ['admin', 'receiving1']:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, date_received, time_received, control_no, source, particulars, received_by, document_receiver, forwarded_to, document_file, created_at, routed_to_receiving2, accepted_by_receiving2 FROM receiving1_documents WHERE DATE(date_received) = CURDATE() ORDER BY created_at DESC")
    recent_documents = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) AS total FROM receiving1_documents")
    total_documents = cursor.fetchone()['total']
    cursor.execute("SELECT COUNT(*) AS today FROM receiving1_documents WHERE DATE(date_received) = CURDATE()")
    documents_today = cursor.fetchone()['today']
    cursor.execute("SELECT COUNT(*) AS total_routed FROM receiving1_documents WHERE routed_to_receiving2 = 1")
    total_routed_to_receiving2 = cursor.fetchone()['total_routed']
    cursor.close()
    conn.close()
    return render_template('receiving1/receiving1_dashboard.html', recent_documents=recent_documents, total_documents=total_documents, documents_today=documents_today, total_routed_to_receiving2=total_routed_to_receiving2)

@app.route('/dashboard/receiving2')
def receiving2_dashboard():
    if session.get('role') not in ['admin', 'receiving2']:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, date_received, time_received, control_no, source, particulars, received_by, document_receiver, forwarded_to, document_file, created_at, routed_to_receiving2, accepted_by_receiving2 FROM receiving1_documents ORDER BY date_received DESC, time_received DESC, created_at DESC")
    documents = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) AS today FROM receiving1_documents WHERE DATE(date_received) = CURDATE() AND routed_to_receiving2 = 1")
    documents_today = cursor.fetchone()['today']
    cursor.execute("SELECT COUNT(*) AS total FROM receiving1_documents WHERE routed_to_receiving2 = 1")
    total_documents = cursor.fetchone()['total']
    # Other documents queries with error handling
    try:
        cursor.execute("SELECT COUNT(*) AS other_today FROM other_documents WHERE DATE(date_received) = CURDATE()")
        other_documents_today = cursor.fetchone()['other_today']
    except:
        other_documents_today = 0
    try:
        cursor.execute("SELECT COUNT(*) AS total_other FROM other_documents")
        total_other_documents = cursor.fetchone()['total_other']
    except:
        total_other_documents = 0
    try:
        # Only fetch other documents received today - exclude document_blob
        cursor.execute("SELECT id, date_received, time_received, control_no, source, particulars, received_by, forwarded_to, document_file, created_at, purpose_action, attachment_file FROM other_documents WHERE DATE(date_received) = CURDATE() ORDER BY date_received DESC, time_received DESC, created_at DESC")
        other_documents = cursor.fetchall()
    except:
        other_documents = []
    cursor.close()
    conn.close()
    # Group documents by date_received
    from collections import defaultdict
    grouped_documents = defaultdict(list)
    for doc in documents:
        grouped_documents[str(doc['date_received'])].append(doc)
    grouped_documents = dict(grouped_documents)
    import datetime
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    return render_template('receiving2/receiving2_dashboard.html', grouped_documents=grouped_documents, documents_today=documents_today, total_documents=total_documents, today_str=today_str, other_documents_today=other_documents_today, other_documents=other_documents, total_other_documents=total_other_documents)

@app.route('/dashboard/docs')
def docs_dashboard():
    if session.get('role') not in ['admin', 'docs']:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS total_gso FROM gso_documents")
    total_gso = cursor.fetchone()['total_gso']
    cursor.execute("SELECT COUNT(*) AS total_travel FROM travel_documents")
    total_travel = cursor.fetchone()['total_travel']
    # Fetch from dedicated tables
    cursor.execute("SELECT COUNT(*) AS total_application_leave FROM application_leave_documents")
    total_application_leave = cursor.fetchone()['total_application_leave']
    cursor.execute("SELECT COUNT(*) AS total_special_permit FROM special_permit_documents")
    total_special_permit = cursor.fetchone()['total_special_permit']
    cursor.close()
    conn.close()
    return render_template('docs/docs_dashboard.html', total_gso=total_gso, total_travel=total_travel, total_application_leave=total_application_leave, total_special_permit=total_special_permit)

@app.route('/dashboard/releasing')
def releasing_dashboard():
    if session.get('role') not in ['admin', 'releasing']:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS total_released FROM outgoing_documents")
    total_released = cursor.fetchone()['total_released']
    cursor.execute("SELECT COUNT(*) AS todays_released FROM outgoing_documents WHERE DATE(date_sent) = CURDATE()")
    todays_released = cursor.fetchone()['todays_released']
    cursor.execute("SELECT id, date_sent, time_sent, control_no, source, particulars, forwarded_to, document_file, created_at FROM outgoing_documents ORDER BY date_sent DESC, time_sent DESC, created_at DESC LIMIT 5")
    recent_outgoing_docs = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('releasing/releasing_dashboard.html', total_released=total_released, todays_released=todays_released, recent_outgoing_docs=recent_outgoing_docs)

@app.route('/releasing/outgoing_docs', methods=['GET', 'POST'])
def releasing_outgoing_docs():
    import datetime
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20  # Number of documents per page
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    success = None
    
    if request.method == 'POST':
        date_sent = request.form['date_sent']
        time_sent = request.form['time_sent']
        control_no = request.form['control_no']
        source = request.form['source']
        particulars = request.form['particulars']
        forwarded_to = request.form['forwarded_to']
        document_file = request.files.get('document_file')
        document_file_name = document_file.filename if document_file else ''
        document_blob = document_file.read() if document_file else None
        created_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute("""
            INSERT INTO outgoing_documents (date_sent, time_sent, control_no, source, particulars, forwarded_to, document_file, document_blob, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (date_sent, time_sent, control_no, source, particulars, forwarded_to, document_file_name, document_blob, created_at))
        conn.commit()
        success = '1'
        return redirect(url_for('releasing_outgoing_docs', success=success))
    
    # Get total count for pagination
    cursor.execute("SELECT COUNT(*) AS total FROM outgoing_documents")
    total_documents = cursor.fetchone()['total']
    
    # Get paginated documents - exclude document_blob
    cursor.execute("""
        SELECT id, date_sent, time_sent, control_no, source, particulars, forwarded_to, document_file, created_at FROM outgoing_documents 
        ORDER BY date_sent DESC, time_sent DESC, created_at DESC 
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    outgoing_docs = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Calculate pagination info
    total_pages = (total_documents + per_page - 1) // per_page
    
    success = request.args.get('success')
    return render_template('releasing/outgoing_docs.html', 
                         outgoing_docs=outgoing_docs, 
                         success=success,
                         # Pagination variables
                         page=page,
                         per_page=per_page,
                         total_pages=total_pages,
                         total_documents=total_documents,
                         has_prev=page > 1,
                         has_next=page < total_pages)

@app.route('/releasing/outgoing_records')
def releasing_outgoing_records():
    from flask import request
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 25  # Number of documents per page
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get total counts
    cursor.execute("SELECT COUNT(*) AS total_outgoing FROM outgoing_documents")
    total_outgoing = cursor.fetchone()['total_outgoing']
    cursor.execute("SELECT COUNT(*) AS total_out_today FROM outgoing_documents WHERE DATE(date_sent) = CURDATE()")
    total_out_today = cursor.fetchone()['total_out_today']
    
    selected_month = request.args.get('month')
    selected_day = request.args.get('day')
    filtered_outgoing = []
    all_outgoing = []
    
    if selected_day:
        # Get total count for selected day
        cursor.execute("""
            SELECT COUNT(*) AS total_filtered FROM outgoing_documents
            WHERE date_sent = %s
        """, (selected_day,))
        total_filtered = cursor.fetchone()['total_filtered']
        
        # Get paginated results for selected day - exclude document_blob
        cursor.execute("""
            SELECT id, date_sent, time_sent, control_no, source, particulars, forwarded_to, document_file, created_at FROM outgoing_documents
            WHERE date_sent = %s
            ORDER BY date_sent DESC, time_sent DESC, created_at DESC
            LIMIT %s OFFSET %s
        """, (selected_day, per_page, offset))
        filtered_outgoing = cursor.fetchall()
        
        # Calculate pagination for filtered results
        total_pages = (total_filtered + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
        
    elif selected_month:
        # Get total count for selected month
        cursor.execute("""
            SELECT COUNT(*) AS total_filtered FROM outgoing_documents
            WHERE DATE_FORMAT(date_sent, '%Y-%m') = %s
        """, (selected_month,))
        total_filtered = cursor.fetchone()['total_filtered']
        
        # Get paginated results for selected month - exclude document_blob
        cursor.execute("""
            SELECT id, date_sent, time_sent, control_no, source, particulars, forwarded_to, document_file, created_at FROM outgoing_documents
            WHERE DATE_FORMAT(date_sent, '%Y-%m') = %s
            ORDER BY date_sent DESC, time_sent DESC, created_at DESC
            LIMIT %s OFFSET %s
        """, (selected_month, per_page, offset))
        filtered_outgoing = cursor.fetchall()
        
        # Calculate pagination for filtered results
        total_pages = (total_filtered + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
        
    else:
        # Get paginated results for all documents - exclude document_blob
        cursor.execute("""
            SELECT id, date_sent, time_sent, control_no, source, particulars, forwarded_to, document_file, created_at FROM outgoing_documents
            ORDER BY date_sent DESC, time_sent DESC, created_at DESC
            LIMIT %s OFFSET %s
        """, (per_page, offset))
        all_outgoing = cursor.fetchall()
        
        # Calculate pagination for all results
        total_pages = (total_outgoing + per_page - 1) // per_page
        has_prev = page > 1
        has_next = page < total_pages
    
    cursor.close()
    conn.close()
    
    return render_template('releasing/outgoing_records.html', 
                         total_outgoing=total_outgoing, 
                         total_out_today=total_out_today, 
                         selected_month=selected_month, 
                         selected_day=selected_day, 
                         filtered_outgoing=filtered_outgoing, 
                         all_outgoing=all_outgoing,
                         # Pagination variables
                         page=page,
                         per_page=per_page,
                         total_pages=total_pages,
                         has_prev=has_prev,
                         has_next=has_next)

@app.route('/docs/gso', methods=['GET', 'POST'])
def docs_gso():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    success = None
    if request.method == 'POST':
        date = request.form['date']
        supplier_name = request.form["supplier_name"]
        office = request.form["office"]
        amount = request.form["amount"]
        forwarded_to = request.form["forwarded_to"]
        document_file = request.files.get('document_file')
        document_file_name = document_file.filename if document_file else ''
        document_blob = document_file.read() if document_file else None
        cursor.execute("""
            INSERT INTO gso_documents (date, supplier_name, office, amount, forwarded_to, document_file, document_blob)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (date, supplier_name, office, amount, forwarded_to, document_file_name, document_blob))
        conn.commit()
        success = '1'
    # Add counts for today, this month, and all time
    cursor.execute("SELECT COUNT(*) AS total_gso_today FROM gso_documents WHERE DATE(date) = CURDATE()")
    total_gso_today = cursor.fetchone()['total_gso_today']
    cursor.execute("SELECT COUNT(*) AS total_gso_month FROM gso_documents WHERE MONTH(date) = MONTH(CURDATE()) AND YEAR(date) = YEAR(CURDATE())")
    total_gso_month = cursor.fetchone()['total_gso_month']
    cursor.execute("SELECT COUNT(*) AS total_gso_all FROM gso_documents")
    total_gso_all = cursor.fetchone()['total_gso_all']
    cursor.execute("SELECT id, date, supplier_name, office, amount, forwarded_to, document_file, created_at FROM gso_documents WHERE DATE(date) = CURDATE() ORDER BY date DESC")
    gso_docs = cursor.fetchall()
    cursor.execute("SELECT id, date, supplier_name, office, amount, forwarded_to, document_file, created_at FROM gso_documents ORDER BY date DESC")
    gso_docs_all = cursor.fetchall()
    cursor.execute("SELECT id, date, supplier_name, office, amount, forwarded_to, document_file, created_at FROM gso_documents WHERE DATE(date) = CURDATE() ORDER BY created_at DESC")
    gso_docs_daily = cursor.fetchall()
    cursor.execute("SELECT id, date, supplier_name, office, amount, forwarded_to, document_file, created_at FROM gso_documents WHERE MONTH(date) = MONTH(CURDATE()) AND YEAR(date) = YEAR(CURDATE()) ORDER BY created_at DESC")
    gso_docs_monthly = cursor.fetchall()
    cursor.close()
    conn.close()
    import datetime
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    return render_template('docs/gso.html', gso_docs=gso_docs, gso_docs_all=gso_docs_all, gso_docs_daily=gso_docs_daily, gso_docs_monthly=gso_docs_monthly, total_gso_today=total_gso_today, total_gso_month=total_gso_month, total_gso_all=total_gso_all, today_str=today_str, success=success)

@app.route('/docs/travel', methods=['GET', 'POST'])
def docs_travel():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    success = None
    if request.method == 'POST':
        name_of_travelling = request.form['name_of_travelling']
        date = request.form['date']
        destination = request.form['destination']
        forwarded_to = request.form['forwarded_to']
        document_file = request.files.get('document_file')
        document_file_name = document_file.filename if document_file else ''
        document_blob = document_file.read() if document_file else None
        cursor.execute("""
            INSERT INTO travel_documents (name_of_travelling, date, destination, forwarded_to, document_file, document_blob)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (name_of_travelling, date, destination, forwarded_to, document_file_name, document_blob))
        conn.commit()
        success = '1'
    cursor.execute("SELECT COUNT(*) AS total_travel_today FROM travel_documents WHERE DATE(date) = CURDATE()")
    total_travel_today = cursor.fetchone()['total_travel_today']
    cursor.execute("SELECT COUNT(*) AS total_travel_month FROM travel_documents WHERE MONTH(date) = MONTH(CURDATE()) AND YEAR(date) = YEAR(CURDATE())")
    total_travel_month = cursor.fetchone()['total_travel_month']
    cursor.execute("SELECT COUNT(*) AS total_travel_all FROM travel_documents")
    total_travel_all = cursor.fetchone()['total_travel_all']
    cursor.execute("SELECT id, name_of_travelling, date, destination, forwarded_to, document_file, created_at FROM travel_documents WHERE DATE(date) = CURDATE() ORDER BY date DESC")
    travel_docs = cursor.fetchall()
    cursor.execute("SELECT id, name_of_travelling, date, destination, forwarded_to, document_file, created_at FROM travel_documents ORDER BY date DESC")
    travel_docs_all = cursor.fetchall()
    cursor.execute("SELECT id, name_of_travelling, date, destination, forwarded_to, document_file, created_at FROM travel_documents WHERE DATE(date) = CURDATE() ORDER BY created_at DESC")
    travel_docs_daily = cursor.fetchall()
    cursor.execute("SELECT id, name_of_travelling, date, destination, forwarded_to, document_file, created_at FROM travel_documents WHERE MONTH(date) = MONTH(CURDATE()) AND YEAR(date) = YEAR(CURDATE()) ORDER BY created_at DESC")
    travel_docs_monthly = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('docs/travel.html', travel_docs=travel_docs, travel_docs_all=travel_docs_all, total_travel_today=total_travel_today, total_travel_month=total_travel_month, total_travel_all=total_travel_all, travel_docs_daily=travel_docs_daily, travel_docs_monthly=travel_docs_monthly, success=success)

@app.route('/docs/special_permit', methods=['GET', 'POST'])
def docs_special_permit():
    import datetime
    success = None
    if request.method == 'POST':
        date = request.form['date']
        name_of_applicant = request.form['name_of_applicant']
        purpose = request.form['purpose']
        duration = request.form['duration']
        forwarded_to = request.form['forwarded_to']
        document_file = request.files.get('document_file')
        document_file_name = document_file.filename if document_file else ''
        document_blob = document_file.read() if document_file else None
        created_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO special_permit_documents (date, name_of_applicant, purpose, duration, forwarded_to, document_file, document_blob, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (date, name_of_applicant, purpose, duration, forwarded_to, document_file_name, document_blob, created_at))
        conn.commit()
        cursor.close()
        conn.close()
        success = '1'
        return redirect(url_for('docs_special_permit', success=success))
    # Fetch stats for cards (today, all time) and document lists
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS total_special_permit_today FROM special_permit_documents WHERE DATE(date) = CURDATE()")
    total_special_permit_today = cursor.fetchone()['total_special_permit_today']
    cursor.execute("SELECT COUNT(*) AS total_special_permit_all FROM special_permit_documents")
    total_special_permit_all = cursor.fetchone()['total_special_permit_all']
    cursor.execute("SELECT id, date, name_of_applicant, purpose, duration, forwarded_to, document_file, created_at FROM special_permit_documents WHERE DATE(date) = CURDATE() ORDER BY date DESC")
    special_permit_docs = cursor.fetchall()
    cursor.execute("SELECT id, date, name_of_applicant, purpose, duration, forwarded_to, document_file, created_at FROM special_permit_documents ORDER BY date DESC")
    special_permit_docs_all = cursor.fetchall()
    cursor.execute("SELECT id, date, name_of_applicant, purpose, duration, forwarded_to, document_file, created_at FROM special_permit_documents WHERE DATE(date) = CURDATE() ORDER BY created_at DESC")
    special_permit_docs_daily = cursor.fetchall()
    cursor.execute("SELECT id, date, name_of_applicant, purpose, duration, forwarded_to, document_file, created_at FROM special_permit_documents WHERE MONTH(date) = MONTH(CURDATE()) AND YEAR(date) = YEAR(CURDATE()) ORDER BY created_at DESC")
    special_permit_docs_monthly = cursor.fetchall()
    cursor.close()
    conn.close()
    success = request.args.get('success')
    return render_template('docs/special_permit.html', total_special_permit_today=total_special_permit_today, total_special_permit_all=total_special_permit_all, success=success, special_permit_docs=special_permit_docs, special_permit_docs_all=special_permit_docs_all, special_permit_docs_daily=special_permit_docs_daily, special_permit_docs_monthly=special_permit_docs_monthly)

@app.route('/docs/application_leave', methods=['GET', 'POST'])
def docs_application_leave():
    import datetime
    success = None
    if request.method == 'POST':
        control_no = request.form['control_no']
        name_of_applicant = request.form['name_of_applicant']
        type_of_leave = request.form['type_of_leave']
        inclusive_date = request.form['inclusive_date']
        forwarded_to = request.form['forwarded_to']
        document_file = request.files.get('document_file')
        document_file_name = document_file.filename if document_file else ''
        document_blob = document_file.read() if document_file else None
        created_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO application_leave_documents (control_no, name_of_applicant, type_of_leave, inclusive_date, forwarded_to, document_file, document_blob, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (control_no, name_of_applicant, type_of_leave, inclusive_date, forwarded_to, document_file_name, document_blob, created_at))
        conn.commit()
        cursor.close()
        conn.close()
        success = '1'
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT COUNT(*) AS total_application_leave_today FROM application_leave_documents WHERE DATE(created_at) = CURDATE()")
    total_application_leave_today = cursor.fetchone()['total_application_leave_today']
    cursor.execute("SELECT COUNT(*) AS total_application_leave_all FROM application_leave_documents")
    total_application_leave_all = cursor.fetchone()['total_application_leave_all']
    cursor.execute("SELECT id, control_no, name_of_applicant, type_of_leave, inclusive_date, forwarded_to, document_file, created_at FROM application_leave_documents WHERE DATE(created_at) = CURDATE() ORDER BY created_at DESC")
    application_leave_docs = cursor.fetchall()
    cursor.execute("SELECT id, control_no, name_of_applicant, type_of_leave, inclusive_date, forwarded_to, document_file, created_at FROM application_leave_documents ORDER BY created_at DESC")
    application_leave_docs_all = cursor.fetchall()
    cursor.execute("SELECT id, control_no, name_of_applicant, type_of_leave, inclusive_date, forwarded_to, document_file, created_at FROM application_leave_documents WHERE DATE(created_at) = CURDATE() ORDER BY created_at DESC")
    application_leave_docs_daily = cursor.fetchall()
    cursor.execute("SELECT id, control_no, name_of_applicant, type_of_leave, inclusive_date, forwarded_to, document_file, created_at FROM application_leave_documents WHERE MONTH(created_at) = MONTH(CURDATE()) AND YEAR(created_at) = YEAR(CURDATE()) ORDER BY created_at DESC")
    application_leave_docs_monthly = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('docs/application_leave.html', total_application_leave_today=total_application_leave_today, total_application_leave_all=total_application_leave_all, success=success, application_leave_docs=application_leave_docs, application_leave_docs_all=application_leave_docs_all, application_leave_docs_daily=application_leave_docs_daily, application_leave_docs_monthly=application_leave_docs_monthly)

@app.route('/docs/gso/preview/<int:doc_id>')
def preview_gso_file(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT document_file, document_blob FROM gso_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['document_blob']:
        filename = doc['document_file']
        # Guess content type
        if filename and filename.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        elif filename and filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif filename and filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif filename and filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        else:
            content_type = 'application/octet-stream'
        response = make_response(doc['document_blob'])
        response.headers.set('Content-Type', content_type)
        
        # Properly encode filename for Content-Disposition header to avoid multiple headers issue
        import urllib.parse
        safe_filename = urllib.parse.quote(filename)
        response.headers.set('Content-Disposition', f'inline; filename="{safe_filename}"')
        
        return response
    return 'File not found', 404

# Docs Document Folder Routes
@app.route('/docs/docs_folder', methods=['GET', 'POST'])
def docs_docs_folder():
    if session.get('role') not in ['admin', 'docs']:
        return redirect(url_for('login'))
    
    success = None
    error = None
    
    # Check for session-based success message
    if session.get('upload_success'):
        success = True
        session.pop('upload_success', None)
    
    if session.get('edit_success'):
        success = True
        session.pop('edit_success', None)  # Clear the session flag
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        try:
            folder_name = request.form['folder_name']
            folder_description = request.form.get('folder_description', '')
            document_files = request.files.getlist('document_files')
            
            if not folder_name or not document_files or all(f.filename == '' for f in document_files):
                error = "Please provide a folder name and select at least one file."
            else:
                # Insert folder
                cursor.execute("""
                    INSERT INTO docs_document_folders (folder_name, folder_description, created_by)
                    VALUES (%s, %s, %s)
                """, (folder_name, folder_description, session.get('username')))
                
                folder_id = cursor.lastrowid
                file_count = 0
                
                # Insert files
                for file in document_files:
                    if file.filename:
                        file_data = file.read()
                        cursor.execute("""
                            INSERT INTO docs_folder_files (folder_id, file_name, file_type, file_size, file_data, uploaded_by)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (folder_id, file.filename, file.content_type, len(file_data), file_data, session.get('username')))
                        file_count += 1
                
                # Update file count
                cursor.execute("UPDATE docs_document_folders SET file_count = %s WHERE id = %s", (file_count, folder_id))
                conn.commit()
                
                # Use session for success message
                session['upload_success'] = True
                return redirect(url_for('docs_docs_folder'))
                
        except Exception as e:
            conn.rollback()
            error = f"Error uploading folder: {str(e)}"
        finally:
            cursor.close()
            conn.close()
    
    # Get folders with file counts
    cursor.execute("""
        SELECT f.*, COUNT(ff.id) as file_count 
        FROM docs_document_folders f 
        LEFT JOIN docs_folder_files ff ON f.id = ff.folder_id 
        GROUP BY f.id 
        ORDER BY f.created_at DESC
    """)
    folders = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('docs/docs_folder.html', folders=folders, success=success, error=error, active_page='docs_docs_folder')

@app.route('/docs/folder/<int:folder_id>')
def docs_view_folder_contents(folder_id):
    if session.get('role') not in ['admin', 'docs']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get folder info
    cursor.execute("SELECT * FROM docs_document_folders WHERE id = %s", (folder_id,))
    folder = cursor.fetchone()
    
    if not folder:
        cursor.close()
        conn.close()
        return 'Folder not found', 404
    
    # Get files in folder
    cursor.execute("SELECT * FROM docs_folder_files WHERE folder_id = %s ORDER BY uploaded_at DESC", (folder_id,))
    files = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('docs/folder_contents.html', folder=folder, files=files, active_page='docs_docs_folder')

@app.route('/docs/search_folders')
def docs_search_folders():
    if session.get('role') not in ['admin', 'docs']:
        return jsonify({'folders': [], 'files': []})
    
    search_term = request.args.get('q', '').strip()
    if not search_term:
        return jsonify({'folders': [], 'files': []})
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Split search terms for fuzzy search
    search_words = search_term.split()
    
    # Build folder search conditions
    folder_conditions = []
    folder_params = []
    
    # Original exact match for backward compatibility
    folder_conditions.append("(f.folder_name LIKE %s OR f.folder_description LIKE %s)")
    folder_params.extend([f'%{search_term}%', f'%{search_term}%'])
    
    # Fuzzy search: check if all words are present in folder name or description
    if len(search_words) > 1:
        folder_word_conditions = []
        for word in search_words:
            folder_word_conditions.append("(f.folder_name LIKE %s OR f.folder_description LIKE %s)")
            folder_params.extend([f'%{word}%', f'%{word}%'])
        folder_conditions.append(f"({' AND '.join(folder_word_conditions)})")
    
    # Search folders
    folder_query = f"""
        SELECT f.*, COUNT(ff.id) as file_count 
        FROM docs_document_folders f 
        LEFT JOIN docs_folder_files ff ON f.id = ff.folder_id 
        WHERE {' OR '.join(folder_conditions)}
        GROUP BY f.id 
        ORDER BY f.created_at DESC
    """
    cursor.execute(folder_query, folder_params)
    folders = cursor.fetchall()
    
    # Build file search conditions
    file_conditions = []
    file_params = []
    
    # Original exact match for backward compatibility
    file_conditions.append("ff.file_name LIKE %s")
    file_params.append(f'%{search_term}%')
    
    # Fuzzy search: check if all words are present in filename
    if len(search_words) > 1:
        file_word_conditions = []
        for word in search_words:
            file_word_conditions.append("ff.file_name LIKE %s")
            file_params.append(f'%{word}%')
        file_conditions.append(f"({' AND '.join(file_word_conditions)})")
    
    # Search files
    file_query = f"""
        SELECT ff.*, f.folder_name, f.id as folder_id
        FROM docs_folder_files ff
        JOIN docs_document_folders f ON ff.folder_id = f.id
        WHERE {' OR '.join(file_conditions)}
        ORDER BY ff.uploaded_at DESC
    """
    cursor.execute(file_query, file_params)
    files = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({'folders': folders, 'files': files})

@app.route('/docs/folder/<int:folder_id>/download/<int:file_id>')
def docs_download_folder_file(folder_id, file_id):
    if session.get('role') not in ['admin', 'docs']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM docs_folder_files WHERE id = %s AND folder_id = %s", (file_id, folder_id))
    file = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if file and file['file_data']:
        response = make_response(file['file_data'])
        response.headers.set('Content-Type', file['file_type'] or 'application/octet-stream')
        
        # Properly encode filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(file['file_name'])
        response.headers.set('Content-Disposition', f'attachment; filename="{safe_filename}"')
        
        return response
    return 'File not found', 404

@app.route('/docs/folder/<int:folder_id>/preview/<int:file_id>')
def docs_preview_folder_file(folder_id, file_id):
    if session.get('role') not in ['admin', 'docs']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM docs_folder_files WHERE id = %s AND folder_id = %s", (file_id, folder_id))
    file = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if file and file['file_data']:
        filename = file['file_name']
        # Guess content type
        if filename.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        elif filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        else:
            content_type = file['file_type'] or 'application/octet-stream'
        
        response = make_response(file['file_data'])
        response.headers.set('Content-Type', content_type)
        
        # Properly encode filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(filename)
        response.headers.set('Content-Disposition', f'inline; filename="{safe_filename}"')
        
        return response
    return 'File not found', 404

@app.route('/receiving1/add_document', methods=['GET', 'POST'])
def receiving1_add_document():
    if session.get('role') not in ['admin', 'receiving1']:
        return redirect(url_for('login'))
    success = None
    if request.method == 'POST':
        date_received = request.form['date_received']
        time_received = request.form['time_received']
        control_no = request.form['control_no']
        source = request.form['source']
        particulars = request.form['particulars']
        received_by = request.form['received_by']
        document_receiver = request.form.get('document_receiver', '')
        forwarded_to = request.form['forwarded_to']
        document_file = request.files.get('document_file')
        document_file_name = document_file.filename if document_file else ''
        document_blob = document_file.read() if document_file else None
        created_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        route_receiving2 = 1 if request.form.get('route_receiving2') == 'on' else 0
        
        # Handle manual time input - convert to proper format or store as is
        try:
            # Try to parse the time input and convert to MySQL TIME format
            if time_received:
                # Handle various time formats
                time_lower = time_received.lower().strip()
                if 'pm' in time_lower or 'am' in time_lower:
                    # Convert 12-hour format to 24-hour format
                    time_parts = time_lower.replace('am', '').replace('pm', '').strip().split(':')
                    hour = int(time_parts[0])
                    minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                    
                    if 'pm' in time_lower and hour != 12:
                        hour += 12
                    elif 'am' in time_lower and hour == 12:
                        hour = 0
                    
                    time_received = f"{hour:02d}:{minute:02d}:00"
                else:
                    # Assume it's already in 24-hour format or just store as is
                    if ':' in time_received:
                        time_parts = time_received.split(':')
                        if len(time_parts) >= 2:
                            hour = int(time_parts[0])
                            minute = int(time_parts[1])
                            time_received = f"{hour:02d}:{minute:02d}:00"
            else:
                time_received = "00:00:00"
        except:
            # If parsing fails, store the original input as is
            time_received = time_received or "00:00:00"
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO receiving1_documents (date_received, time_received, control_no, source, particulars, received_by, document_receiver, forwarded_to, document_file, document_blob, created_at, routed_to_receiving2)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (date_received, time_received, control_no, source, particulars, received_by, document_receiver, forwarded_to, document_file_name, document_blob, created_at, route_receiving2))
        receiving1_id = cursor.lastrowid
        if route_receiving2:
            cursor.execute("""
                INSERT INTO receiving2_documents (
                    original_receiving1_id, date_received, time_received, control_no, source, particulars, received_by, forwarded_to, document_file, document_blob, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                receiving1_id, date_received, time_received, control_no, source, particulars, received_by, forwarded_to, document_file_name, document_blob, created_at
            ))
        conn.commit()
        cursor.close()
        conn.close()
        success = '1'
        # Use PRG pattern to avoid resubmission on refresh
        return redirect(url_for('receiving1_add_document', success=success))
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20  # Number of documents per page
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get total count for pagination
    cursor.execute("SELECT COUNT(*) AS total FROM receiving1_documents")
    total_documents = cursor.fetchone()['total']
    
    # Get paginated documents - exclude document_blob
    cursor.execute("SELECT id, date_received, time_received, control_no, source, particulars, received_by, document_receiver, forwarded_to, document_file, created_at, routed_to_receiving2, accepted_by_receiving2 FROM receiving1_documents ORDER BY created_at DESC LIMIT %s OFFSET %s", (per_page, offset))
    documents = cursor.fetchall()
    cursor.close()
    conn.close()
    
    # Calculate pagination info
    total_pages = (total_documents + per_page - 1) // per_page
    
    if request.method == 'POST' and success == '1':
        return render_template('receiving1/add_document.html', 
                             documents=documents, 
                             success=success,
                             # Pagination variables
                             page=page,
                             per_page=per_page,
                             total_pages=total_pages,
                             total_documents=total_documents,
                             has_prev=page > 1,
                             has_next=page < total_pages), 200
    success = request.args.get('success')
    return render_template('receiving1/add_document.html', 
                         documents=documents, 
                         success=success,
                         # Pagination variables
                         page=page,
                         per_page=per_page,
                         total_pages=total_pages,
                         total_documents=total_documents,
                         has_prev=page > 1,
                         has_next=page < total_pages)

@app.route('/receiving1/download/<int:doc_id>')
def download_receiving1_file(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT document_file, document_blob FROM receiving1_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['document_blob']:
        response = make_response(doc['document_blob'])
        response.headers.set('Content-Type', 'application/octet-stream')
        # Properly encode filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(doc['document_file'])
        response.headers.set('Content-Disposition', f'attachment; filename="{safe_filename}"')
        return response
    return 'File not found', 404

@app.route('/receiving1/preview/<int:doc_id>')
def preview_receiving1_file(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT document_file, document_blob FROM receiving1_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not doc:
        return 'Document not found', 404
    
    if not doc['document_blob']:
        return 'Document file is empty or corrupted', 404
    
    filename = doc['document_file']
    if not filename:
        return 'Document filename is missing', 404
    
    # Guess content type
    if filename.lower().endswith('.pdf'):
        content_type = 'application/pdf'
    elif filename.lower().endswith(('.jpg', '.jpeg')):
        content_type = 'image/jpeg'
    elif filename.lower().endswith('.png'):
        content_type = 'image/png'
    elif filename.lower().endswith('.gif'):
        content_type = 'image/gif'
    elif filename.lower().endswith(('.doc', '.docx')):
        content_type = 'application/msword'
    elif filename.lower().endswith('.txt'):
        content_type = 'text/plain'
    else:
        content_type = 'application/octet-stream'
    
    response = make_response(doc['document_blob'])
    response.headers.set('Content-Type', content_type)
    
    # Properly encode filename for Content-Disposition header
    import urllib.parse
    safe_filename = urllib.parse.quote(filename)
    response.headers.set('Content-Disposition', f'inline; filename="{safe_filename}"')
    
    # Add cache control headers to prevent caching issues
    response.headers.set('Cache-Control', 'no-cache, no-store, must-revalidate')
    response.headers.set('Pragma', 'no-cache')
    response.headers.set('Expires', '0')
    
    return response

@app.route('/receiving1/edit/<int:doc_id>', methods=['GET', 'POST'])
def edit_receiving1_document(doc_id):
    if session.get('role') not in ['admin', 'receiving1']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        try:
            date_received = request.form['date_received']
            time_received = request.form['time_received']
            control_no = request.form['control_no']
            source = request.form['source']
            particulars = request.form['particulars']
            received_by = request.form['received_by']
            document_receiver = request.form.get('document_receiver', '')
            forwarded_to = request.form['forwarded_to']
            route_receiving2 = 1 if request.form.get('route_receiving2') == 'on' else 0
            
            # Handle manual time input - convert to proper format or store as is
            try:
                # Try to parse the time input and convert to MySQL TIME format
                if time_received:
                    # Handle various time formats
                    time_lower = time_received.lower().strip()
                    if 'pm' in time_lower or 'am' in time_lower:
                        # Convert 12-hour format to 24-hour format
                        time_parts = time_lower.replace('am', '').replace('pm', '').strip().split(':')
                        hour = int(time_parts[0])
                        minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                        
                        if 'pm' in time_lower and hour != 12:
                            hour += 12
                        elif 'am' in time_lower and hour == 12:
                            hour = 0
                        
                        time_received = f"{hour:02d}:{minute:02d}:00"
                    else:
                        # Assume it's already in 24-hour format or just store as is
                        if ':' in time_received:
                            time_parts = time_received.split(':')
                            if len(time_parts) >= 2:
                                hour = int(time_parts[0])
                                minute = int(time_parts[1])
                                time_received = f"{hour:02d}:{minute:02d}:00"
                else:
                    time_received = "00:00:00"
            except:
                # If parsing fails, store the original input as is
                time_received = time_received or "00:00:00"
            
            # Handle file upload if new file is provided
            document_file = request.files.get('document_file')
            if document_file and document_file.filename:
                document_file_name = document_file.filename
                document_blob = document_file.read()
                cursor.execute("""
                    UPDATE receiving1_documents 
                    SET date_received = %s, time_received = %s, control_no = %s, source = %s, 
                        particulars = %s, received_by = %s, document_receiver = %s, forwarded_to = %s, 
                        document_file = %s, document_blob = %s, routed_to_receiving2 = %s
                    WHERE id = %s
                """, (date_received, time_received, control_no, source, particulars, 
                      received_by, document_receiver, forwarded_to, document_file_name, document_blob, route_receiving2, doc_id))
            else:
                cursor.execute("""
                    UPDATE receiving1_documents 
                    SET date_received = %s, time_received = %s, control_no = %s, source = %s, 
                        particulars = %s, received_by = %s, document_receiver = %s, forwarded_to = %s, routed_to_receiving2 = %s
                    WHERE id = %s
                """, (date_received, time_received, control_no, source, particulars, 
                      received_by, document_receiver, forwarded_to, route_receiving2, doc_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'success': True, 'message': 'Document updated successfully!'})
            
        except Exception as e:
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': f'Error updating document: {str(e)}'})
    
    # GET request - fetch document data - exclude document_blob
    cursor.execute("SELECT id, date_received, time_received, control_no, source, particulars, received_by, document_receiver, forwarded_to, document_file, created_at, routed_to_receiving2, accepted_by_receiving2 FROM receiving1_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not doc:
        return jsonify({'success': False, 'message': 'Document not found'})
    
    return jsonify({
        'success': True,
        'document': {
            'id': doc['id'],
            'date_received': str(doc['date_received']),
            'time_received': str(doc['time_received']) if doc['time_received'] else '',
            'control_no': doc['control_no'],
            'source': doc['source'],
            'particulars': doc['particulars'] if doc['particulars'] else '',
            'received_by': doc['received_by'] if doc['received_by'] else '',
            'document_receiver': doc['document_receiver'] if doc['document_receiver'] else '',
            'forwarded_to': doc['forwarded_to'] if doc['forwarded_to'] else '',
            'document_file': doc['document_file'] if doc['document_file'] else '',
            'routed_to_receiving2': doc['routed_to_receiving2'] if doc['routed_to_receiving2'] else 0
        }
    })

@app.route('/receiving1/document_records')
def receiving1_document_records():
    if session.get('role') not in ['admin', 'receiving1']:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, date_received, time_received, control_no, source, particulars, received_by, document_receiver, forwarded_to, document_file, created_at, routed_to_receiving2, accepted_by_receiving2 FROM receiving1_documents ORDER BY date_received DESC, time_received DESC, created_at DESC")
    all_documents = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) AS monthly FROM receiving1_documents WHERE MONTH(date_received) = MONTH(CURDATE()) AND YEAR(date_received) = YEAR(CURDATE())")
    total_monthly_documents = cursor.fetchone()['monthly']
    cursor.execute("SELECT COUNT(*) AS today FROM receiving1_documents WHERE DATE(date_received) = CURDATE()")
    documents_today = cursor.fetchone()['today']
    cursor.close()
    conn.close()
    return render_template('receiving1/document_records.html', all_documents=all_documents, total_monthly_documents=total_monthly_documents, documents_today=documents_today)

@app.route('/receiving2/document_records')
def receiving2_document_records():
    if session.get('role') not in ['admin', 'receiving2']:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, date_received, time_received, control_no, source, particulars, received_by, document_receiver, forwarded_to, document_file, created_at, routed_to_receiving2, accepted_by_receiving2 FROM receiving1_documents WHERE routed_to_receiving2 = 1 ORDER BY date_received DESC, time_received DESC, created_at DESC")
    all_documents = cursor.fetchall()
    cursor.execute("SELECT COUNT(*) AS monthly FROM receiving1_documents WHERE routed_to_receiving2 = 1 AND MONTH(date_received) = MONTH(CURDATE()) AND YEAR(date_received) = YEAR(CURDATE())")
    total_monthly_documents = cursor.fetchone()['monthly']
    try:
        cursor.execute("SELECT COUNT(*) AS total_other FROM other_documents")
        total_email_documents = cursor.fetchone()['total_other']
    except:
        total_email_documents = 0
    # Fetch all other_documents records - exclude document_blob
    try:
        cursor.execute("SELECT id, date_received, time_received, control_no, source, particulars, received_by, forwarded_to, document_file, created_at, purpose_action, attachment_file FROM other_documents ORDER BY date_received DESC, time_received DESC, created_at DESC")
        other_documents = cursor.fetchall()
    except:
        other_documents = []
    # Fetch all accepted docs from accepted_documents table - exclude document_blob
    try:
        cursor.execute("SELECT id, original_receiving1_id, date_received, time_received, control_no, source, particulars, received_by, forwarded_to, document_file, date_accepted, time_accepted, accepted_by, purposes, remarks, attachment_file, created_at FROM accepted_documents ORDER BY date_accepted DESC, time_accepted DESC, created_at DESC")
        accepted_docs = cursor.fetchall()
        # Get total count for statistics
        cursor.execute("SELECT COUNT(*) AS total_accepted FROM accepted_documents")
        total_accepted_count = cursor.fetchone()['total_accepted']
    except:
        accepted_docs = []
        total_accepted_count = 0
    # Fetch all outgoing documents - exclude document_blob
    try:
        cursor.execute("SELECT id, date_sent, time_sent, control_no, source, particulars, forwarded_to, document_file, created_at, accepted_by_receiving2 FROM outgoing_documents ORDER BY date_sent DESC, time_sent DESC, created_at DESC")
        outgoing_docs = cursor.fetchall()
    except:
        outgoing_docs = []
    # Fetch only accepted outgoing documents - exclude document_blob
    try:
        cursor.execute("SELECT id, date_sent, time_sent, control_no, source, particulars, forwarded_to, document_file, created_at, accepted_by_receiving2 FROM outgoing_documents WHERE accepted_by_receiving2 = 1 ORDER BY date_sent DESC, time_sent DESC, created_at DESC")
        outgoing_accepted_docs = cursor.fetchall()
    except:
        outgoing_accepted_docs = []
    cursor.close()
    conn.close()
    return render_template('receiving2/document_reports.html', all_documents=all_documents, total_monthly_documents=total_monthly_documents, total_email_documents=total_email_documents, other_documents=other_documents, accepted_docs=accepted_docs, total_accepted_count=total_accepted_count, outgoing_docs=outgoing_docs, outgoing_accepted_docs=outgoing_accepted_docs)

@app.route('/receiving2/rts')
def receiving2_rts():
    if session.get('role') not in ['admin', 'receiving2']:
        return redirect(url_for('login'))
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Only show unaccepted documents in recent_documents - exclude document_blob
    cursor.execute("SELECT id, date_received, time_received, control_no, source, particulars, received_by, document_receiver, forwarded_to, document_file, created_at, routed_to_receiving2, accepted_by_receiving2 FROM receiving1_documents WHERE DATE(date_received) = CURDATE() AND routed_to_receiving2 = 1 AND accepted_by_receiving2 = 0 ORDER BY created_at DESC")
    recent_documents = cursor.fetchall()
    # Only show unaccepted documents in all_documents as well - exclude document_blob
    cursor.execute("SELECT id, date_received, time_received, control_no, source, particulars, received_by, document_receiver, forwarded_to, document_file, created_at, routed_to_receiving2, accepted_by_receiving2 FROM receiving1_documents WHERE routed_to_receiving2 = 1 AND accepted_by_receiving2 = 0 ORDER BY date_received DESC, time_received DESC, created_at DESC")
    all_documents = cursor.fetchall()
    # Only show unaccepted other_documents (not yet accepted in receiving2_documents) - exclude document_blob
    try:
        cursor.execute("""
            SELECT id, date_received, time_received, control_no, source, particulars, received_by, forwarded_to, document_file, created_at, purpose_action, attachment_file FROM other_documents od
            WHERE NOT EXISTS (
                SELECT 1 FROM receiving2_documents r2d
                WHERE r2d.original_receiving1_id = od.id
            )
            ORDER BY date_received DESC, time_received DESC, created_at DESC
        """)
        email_documents = cursor.fetchall()
    except:
        email_documents = []
    # Count accepted docs for outgoing docs card
    cursor.execute("SELECT COUNT(*) AS total_outgoing_docs FROM receiving1_documents WHERE accepted_by_receiving2 = 1")
    total_outgoing_docs = cursor.fetchone()['total_outgoing_docs']
    cursor.close()
    conn.close()
    return render_template('receiving2/rts.html', recent_documents=recent_documents, all_documents=all_documents, email_documents=email_documents, total_outgoing_docs=total_outgoing_docs)

@app.route('/manage_users')
def manage_users():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    cursor.close()
    conn.close()
    now = datetime.datetime.utcnow()
    for user in users:
        last_seen = user.get('last_seen')
        if last_seen:
            # Convert to UTC if needed
            if isinstance(last_seen, datetime.datetime):
                delta = now - last_seen
                user['is_online'] = delta.total_seconds() < 300  # 5 minutes
            else:
                user['is_online'] = False
        else:
            user['is_online'] = False
    return render_template('admin/user_management.html', users=users)







@app.route('/admin/upload_document', methods=['GET', 'POST'])
def admin_upload_document():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    success = None
    if request.method == 'POST':
        folder_name = request.form['folder_name']
        folder_description = request.form.get('folder_description', '')
        role = request.form['role']
        document_files = request.files.getlist('document_files')
        if not document_files or not document_files[0].filename:
            flash('Please select at least one file', 'error')
            return redirect(url_for('admin_upload_document'))
        created_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        current_date = datetime.datetime.now().strftime('%Y-%m-%d')
        current_time = datetime.datetime.now().strftime('%H:%M:%S')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Process each uploaded file
        for i, document_file in enumerate(document_files):
            if document_file and document_file.filename:
                document_file_name = document_file.filename
                document_blob = document_file.read()
                
                # Create a unique control number for each file
                file_control_no = f"{folder_name}_file_{i+1}"
                
                cursor.execute("""
                    INSERT INTO receiving1_documents (date_received, time_received, control_no, source, particulars, received_by, forwarded_to, document_file, document_blob, created_at, routed_to_receiving2, role)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (current_date, current_time, file_control_no, folder_name, folder_description, session.get('username', 'Admin'), 'Folder Upload', document_file_name, document_blob, created_at, 0, role))
        
        conn.commit()
        cursor.close()
        conn.close()
        success = '1'
        return redirect(url_for('admin_upload_document', success=success))
    
    success = request.args.get('success')
    
    # Fetch documents for the table - exclude document_blob
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, date_received, time_received, control_no, source, particulars, received_by, document_receiver, forwarded_to, document_file, created_at, routed_to_receiving2, accepted_by_receiving2 FROM receiving1_documents ORDER BY created_at DESC LIMIT 20")
    documents = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('admin/upload_document.html', success=success, documents=documents)

@app.route('/admin/document_browser')
def admin_document_browser():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get unique folders grouped by source (folder name)
    cursor.execute("""
        SELECT 
            source as name,
            COUNT(*) as file_count,
            MAX(role) as role,
            MAX(date_received) as date
        FROM receiving1_documents 
        WHERE source IS NOT NULL AND source != ''
        GROUP BY source 
        ORDER BY MAX(date_received) DESC
    """)
    folders = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('admin/document_browser.html', folders=folders)

@app.route('/receiving1/document_folder', methods=['GET', 'POST'])
def receiving1_document_folder():
    if session.get('role') not in ['admin', 'receiving1']:
        return redirect(url_for('login'))
    
    success = None
    error = None
    
    if request.method == 'POST':
        folder_name = request.form['folder_name']
        folder_description = request.form.get('folder_description', '')
        document_files = request.files.getlist('document_files')
        
        if not document_files or not document_files[0].filename:
            error = 'Please select at least one file'
        else:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                # First, create the folder
                cursor.execute("""
                    INSERT INTO document_folders (folder_name, folder_description, created_by)
                    VALUES (%s, %s, %s)
                """, (folder_name, folder_description, session.get('username', 'User')))
                
                folder_id = cursor.lastrowid
                
                # Process each uploaded file
                for document_file in document_files:
                    if document_file and document_file.filename:
                        file_name = document_file.filename
                        file_blob = document_file.read()
                        file_size = len(file_blob)
                        file_type = document_file.content_type or 'application/octet-stream'
                        
                        cursor.execute("""
                            INSERT INTO folder_files (folder_id, file_name, file_blob, file_size, file_type, uploaded_by)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (folder_id, file_name, file_blob, file_size, file_type, session.get('username', 'User')))
                
                conn.commit()
                cursor.close()
                conn.close()
                session['upload_success'] = True
                return redirect(url_for('receiving1_document_folder'))
                
            except Exception as e:
                error = f'Error uploading folder: {str(e)}'
                if 'conn' in locals():
                    conn.rollback()
                    cursor.close()
                    conn.close()
    
    # Check for success message from session
    success = None
    if session.get('upload_success'):
        success = True
        session.pop('upload_success', None)  # Clear the session flag
    
    if session.get('edit_success'):
        success = True
        session.pop('edit_success', None)  # Clear the session flag
    
    # Fetch folders for display
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get folders with file counts
    cursor.execute("""
        SELECT 
            df.id,
            df.folder_name as name,
            df.folder_description,
            df.created_at as date,
            COUNT(ff.id) as file_count
        FROM document_folders df
        LEFT JOIN folder_files ff ON df.id = ff.folder_id
        GROUP BY df.id, df.folder_name, df.folder_description, df.created_at
        ORDER BY df.created_at DESC
    """)
    folders = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('receiving1/document_folder.html', folders=folders, success=success, error=error, active_page='document_folder')

@app.route('/receiving1/edit_folder/<int:folder_id>', methods=['GET', 'POST'])
def edit_receiving1_folder(folder_id):
    if session.get('role') not in ['admin', 'receiving1']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get folder details
    cursor.execute("SELECT * FROM document_folders WHERE id = %s", (folder_id,))
    folder = cursor.fetchone()
    
    if not folder:
        cursor.close()
        conn.close()
        return 'Folder not found', 404
    
    if request.method == 'POST':
        folder_name = request.form['folder_name']
        folder_description = request.form.get('folder_description', '')
        
        try:
            cursor.execute("""
                UPDATE document_folders 
                SET folder_name = %s, folder_description = %s, updated_at = NOW()
                WHERE id = %s
            """, (folder_name, folder_description, folder_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            session['edit_success'] = True
            return redirect(url_for('receiving1_document_folder'))
            
        except Exception as e:
            error = f'Error updating folder: {str(e)}'
            conn.rollback()
            cursor.close()
            conn.close()
            return render_template('receiving1/edit_folder.html', folder=folder, error=error)
    
    cursor.close()
    conn.close()
    return render_template('receiving1/edit_folder.html', folder=folder)

@app.route('/receiving2/edit_folder/<int:folder_id>', methods=['GET', 'POST'])
def edit_receiving2_folder(folder_id):
    if session.get('role') not in ['admin', 'receiving2']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get folder details
    cursor.execute("SELECT * FROM document_folders WHERE id = %s", (folder_id,))
    folder = cursor.fetchone()
    
    if not folder:
        cursor.close()
        conn.close()
        return 'Folder not found', 404
    
    if request.method == 'POST':
        folder_name = request.form['folder_name']
        folder_description = request.form.get('folder_description', '')
        
        try:
            cursor.execute("""
                UPDATE document_folders 
                SET folder_name = %s, folder_description = %s, updated_at = NOW()
                WHERE id = %s
            """, (folder_name, folder_description, folder_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            session['edit_success'] = True
            return redirect(url_for('receiving2_document_folder'))
            
        except Exception as e:
            error = f'Error updating folder: {str(e)}'
            conn.rollback()
            cursor.close()
            conn.close()
            return render_template('receiving2/edit_folder.html', folder=folder, error=error)
    
    cursor.close()
    conn.close()
    return render_template('receiving2/edit_folder.html', folder=folder)

@app.route('/releasing/edit_folder/<int:folder_id>', methods=['GET', 'POST'])
def edit_releasing_folder(folder_id):
    if session.get('role') not in ['admin', 'releasing']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get folder details
    cursor.execute("SELECT * FROM releasing_document_folders WHERE id = %s", (folder_id,))
    folder = cursor.fetchone()
    
    if not folder:
        cursor.close()
        conn.close()
        return 'Folder not found', 404
    
    if request.method == 'POST':
        folder_name = request.form['folder_name']
        folder_description = request.form.get('folder_description', '')
        
        try:
            cursor.execute("""
                UPDATE releasing_document_folders 
                SET folder_name = %s, folder_description = %s, updated_at = NOW()
                WHERE id = %s
            """, (folder_name, folder_description, folder_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            session['edit_success'] = True
            return redirect(url_for('releasing_outgoing_folder'))
            
        except Exception as e:
            error = f'Error updating folder: {str(e)}'
            conn.rollback()
            cursor.close()
            conn.close()
            return render_template('releasing/edit_folder.html', folder=folder, error=error)
    
    cursor.close()
    conn.close()
    return render_template('releasing/edit_folder.html', folder=folder)

@app.route('/docs/edit_folder/<int:folder_id>', methods=['GET', 'POST'])
def edit_docs_folder(folder_id):
    if session.get('role') not in ['admin', 'docs']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get folder details
    cursor.execute("SELECT * FROM docs_document_folders WHERE id = %s", (folder_id,))
    folder = cursor.fetchone()
    
    if not folder:
        cursor.close()
        conn.close()
        return 'Folder not found', 404
    
    if request.method == 'POST':
        folder_name = request.form['folder_name']
        folder_description = request.form.get('folder_description', '')
        
        try:
            cursor.execute("""
                UPDATE docs_document_folders 
                SET folder_name = %s, folder_description = %s, updated_at = NOW()
                WHERE id = %s
            """, (folder_name, folder_description, folder_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            
            session['edit_success'] = True
            return redirect(url_for('docs_docs_folder'))
            
        except Exception as e:
            error = f'Error updating folder: {str(e)}'
            conn.rollback()
            cursor.close()
            conn.close()
            return render_template('docs/edit_folder.html', folder=folder, error=error)
    
    cursor.close()
    conn.close()
    return render_template('docs/edit_folder.html', folder=folder)

@app.route('/receiving1/folder/<int:folder_id>')
def view_folder_contents(folder_id):
    if session.get('role') not in ['admin', 'receiving1']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get folder details
    cursor.execute("SELECT * FROM document_folders WHERE id = %s", (folder_id,))
    folder = cursor.fetchone()
    
    if not folder:
        cursor.close()
        conn.close()
        return 'Folder not found', 404
    
    # Get files in the folder
    cursor.execute("SELECT * FROM folder_files WHERE folder_id = %s ORDER BY uploaded_at DESC", (folder_id,))
    files = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('receiving1/folder_contents.html', folder=folder, files=files, active_page='document_folder')

# Receiving2 Document Folder Routes
@app.route('/receiving2/document_folder')
def redirect_old_receiving2_route():
    return redirect(url_for('receiving2_document_folder'))

@app.route('/receiving2/admin_RC_folder', methods=['GET', 'POST'])
def receiving2_document_folder():
    if session.get('role') not in ['admin', 'receiving2']:
        return redirect(url_for('login'))
    
    success = None
    error = None
    
    if request.method == 'POST':
        folder_name = request.form['folder_name']
        folder_description = request.form.get('folder_description', '')
        document_files = request.files.getlist('document_files')
        
        if not document_files or not document_files[0].filename:
            error = 'Please select at least one file'
        else:
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                
                # First, create the folder
                cursor.execute("""
                    INSERT INTO receiving2_document_folders (folder_name, folder_description, created_by)
                    VALUES (%s, %s, %s)
                """, (folder_name, folder_description, session.get('username', 'User')))
                
                folder_id = cursor.lastrowid
                
                # Process each uploaded file
                for document_file in document_files:
                    if document_file and document_file.filename:
                        file_name = document_file.filename
                        file_blob = document_file.read()
                        file_size = len(file_blob)
                        file_type = document_file.content_type or 'application/octet-stream'
                        
                        cursor.execute("""
                            INSERT INTO receiving2_folder_files (folder_id, file_name, file_blob, file_size, file_type, uploaded_by)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (folder_id, file_name, file_blob, file_size, file_type, session.get('username', 'User')))
                
                conn.commit()
                cursor.close()
                conn.close()
                session['upload_success'] = True
                return redirect(url_for('receiving2_document_folder'))
                
            except Exception as e:
                error = f'Error uploading folder: {str(e)}'
                if 'conn' in locals():
                    conn.rollback()
                    cursor.close()
                    conn.close()
    
    # Check for success message from session
    success = None
    if session.get('upload_success'):
        success = True
        session.pop('upload_success', None)  # Clear the session flag
    
    if session.get('edit_success'):
        success = True
        session.pop('edit_success', None)  # Clear the session flag
    
    # Fetch folders for display
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get folders with file counts
    cursor.execute("""
        SELECT 
            df.id,
            df.folder_name as name,
            df.folder_description,
            df.created_at as date,
            COUNT(ff.id) as file_count
        FROM receiving2_document_folders df
        LEFT JOIN receiving2_folder_files ff ON df.id = ff.folder_id
        GROUP BY df.id, df.folder_name, df.folder_description, df.created_at
        ORDER BY df.created_at DESC
    """)
    folders = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('receiving2/admin_RC_folder.html', folders=folders, success=success, error=error, active_page='receiving2_admin_RC_folder')

@app.route('/receiving2/folder/<int:folder_id>')
def receiving2_view_folder_contents(folder_id):
    if session.get('role') not in ['admin', 'receiving2']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get folder details
    cursor.execute("SELECT * FROM receiving2_document_folders WHERE id = %s", (folder_id,))
    folder = cursor.fetchone()
    
    if not folder:
        cursor.close()
        conn.close()
        return 'Folder not found', 404
    
    # Get files in the folder
    cursor.execute("SELECT * FROM receiving2_folder_files WHERE folder_id = %s ORDER BY uploaded_at DESC", (folder_id,))
    files = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return render_template('receiving2/folder_contents.html', folder=folder, files=files, active_page='receiving2_admin_RC_folder')

@app.route('/receiving2/search_folders')
def receiving2_search_folders():
    if session.get('role') not in ['admin', 'receiving2']:
        return jsonify({'error': 'Unauthorized'}), 401
    
    search_term = request.args.get('q', '').strip()
    if not search_term:
        return jsonify({'folders': [], 'files': []})
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Split search terms for fuzzy search
    search_words = search_term.split()
    
    # Build folder search conditions
    folder_conditions = []
    folder_params = []
    
    # Original exact match for backward compatibility
    folder_conditions.append("(df.folder_name LIKE %s OR df.folder_description LIKE %s)")
    folder_params.extend([f'%{search_term}%', f'%{search_term}%'])
    
    # Fuzzy search: check if all words are present in folder name or description
    if len(search_words) > 1:
        folder_word_conditions = []
        for word in search_words:
            folder_word_conditions.append("(df.folder_name LIKE %s OR df.folder_description LIKE %s)")
            folder_params.extend([f'%{word}%', f'%{word}%'])
        folder_conditions.append(f"({' AND '.join(folder_word_conditions)})")
    
    # Search in folders
    folder_query = f"""
        SELECT df.id, df.folder_name, df.folder_description, df.created_at,
               COUNT(ff.id) as file_count
        FROM receiving2_document_folders df
        LEFT JOIN receiving2_folder_files ff ON df.id = ff.folder_id
        WHERE {' OR '.join(folder_conditions)}
        GROUP BY df.id, df.folder_name, df.folder_description, df.created_at
        ORDER BY df.created_at DESC
    """
    cursor.execute(folder_query, folder_params)
    folders = cursor.fetchall()
    
    # Build file search conditions
    file_conditions = []
    file_params = []
    
    # Original exact match for backward compatibility
    file_conditions.append("ff.file_name LIKE %s")
    file_params.append(f'%{search_term}%')
    
    # Fuzzy search: check if all words are present in filename
    if len(search_words) > 1:
        file_word_conditions = []
        for word in search_words:
            file_word_conditions.append("ff.file_name LIKE %s")
            file_params.append(f'%{word}%')
        file_conditions.append(f"({' AND '.join(file_word_conditions)})")
    
    # Search in files within folders
    file_query = f"""
        SELECT ff.id, ff.file_name, ff.file_size, ff.file_type, ff.uploaded_at, ff.uploaded_by,
               df.id as folder_id, df.folder_name
        FROM receiving2_folder_files ff
        JOIN receiving2_document_folders df ON ff.folder_id = df.id
        WHERE {' OR '.join(file_conditions)}
        ORDER BY ff.uploaded_at DESC
    """
    cursor.execute(file_query, file_params)
    files = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'folders': folders,
        'files': files
    })

@app.route('/receiving2/folder/<int:folder_id>/download/<int:file_id>')
def receiving2_download_folder_file(folder_id, file_id):
    if session.get('role') not in ['admin', 'receiving2']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM receiving2_folder_files WHERE id = %s AND folder_id = %s", (file_id, folder_id))
    file = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if file and file['file_blob']:
        response = make_response(file['file_blob'])
        response.headers.set('Content-Type', 'application/octet-stream')
        # Properly encode filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(file['file_name'])
        response.headers.set('Content-Disposition', f'attachment; filename="{safe_filename}"')
        return response
    return 'File not found', 404

@app.route('/receiving2/folder/<int:folder_id>/preview/<int:file_id>')
def receiving2_preview_folder_file(folder_id, file_id):
    if session.get('role') not in ['admin', 'receiving2']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM receiving2_folder_files WHERE id = %s AND folder_id = %s", (file_id, folder_id))
    file = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if file and file['file_blob']:
        filename = file['file_name']
        # Guess content type
        if filename.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        elif filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        else:
            content_type = file['file_type'] or 'application/octet-stream'
        
        response = make_response(file['file_blob'])
        response.headers.set('Content-Type', content_type)
        
        # Properly encode filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(filename)
        response.headers.set('Content-Disposition', f'inline; filename="{safe_filename}"')
        
        return response
    return 'File not found', 404

@app.route('/receiving1/search_folders')
def search_folders():
    if session.get('role') not in ['admin', 'receiving1']:
        return jsonify({'error': 'Unauthorized'}), 401
    
    search_term = request.args.get('q', '').strip()
    if not search_term:
        return jsonify({'folders': [], 'files': []})
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Split search terms for fuzzy search
    search_words = search_term.split()
    
    # Build folder search conditions
    folder_conditions = []
    folder_params = []
    
    # Original exact match for backward compatibility
    folder_conditions.append("(df.folder_name LIKE %s OR df.folder_description LIKE %s)")
    folder_params.extend([f'%{search_term}%', f'%{search_term}%'])
    
    # Fuzzy search: check if all words are present in folder name or description
    if len(search_words) > 1:
        folder_word_conditions = []
        for word in search_words:
            folder_word_conditions.append("(df.folder_name LIKE %s OR df.folder_description LIKE %s)")
            folder_params.extend([f'%{word}%', f'%{word}%'])
        folder_conditions.append(f"({' AND '.join(folder_word_conditions)})")
    
    # Search in folders
    folder_query = f"""
        SELECT df.id, df.folder_name, df.folder_description, df.created_at,
               COUNT(ff.id) as file_count
        FROM document_folders df
        LEFT JOIN folder_files ff ON df.id = ff.folder_id
        WHERE {' OR '.join(folder_conditions)}
        GROUP BY df.id, df.folder_name, df.folder_description, df.created_at
        ORDER BY df.created_at DESC
    """
    cursor.execute(folder_query, folder_params)
    folders = cursor.fetchall()
    
    # Build file search conditions
    file_conditions = []
    file_params = []
    
    # Original exact match for backward compatibility
    file_conditions.append("ff.file_name LIKE %s")
    file_params.append(f'%{search_term}%')
    
    # Fuzzy search: check if all words are present in filename
    if len(search_words) > 1:
        file_word_conditions = []
        for word in search_words:
            file_word_conditions.append("ff.file_name LIKE %s")
            file_params.append(f'%{word}%')
        file_conditions.append(f"({' AND '.join(file_word_conditions)})")
    
    # Search in files within folders
    file_query = f"""
        SELECT ff.id, ff.file_name, ff.file_size, ff.file_type, ff.uploaded_at, ff.uploaded_by,
               df.id as folder_id, df.folder_name
        FROM folder_files ff
        JOIN document_folders df ON ff.folder_id = df.id
        WHERE {' OR '.join(file_conditions)}
        ORDER BY ff.uploaded_at DESC
    """
    cursor.execute(file_query, file_params)
    files = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({
        'folders': folders,
        'files': files
    })

@app.route('/receiving1/folder/<int:folder_id>/download/<int:file_id>')
def download_folder_file(folder_id, file_id):
    if session.get('role') not in ['admin', 'receiving1']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM folder_files WHERE id = %s AND folder_id = %s", (file_id, folder_id))
    file = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if file and file['file_blob']:
        response = make_response(file['file_blob'])
        response.headers.set('Content-Type', 'application/octet-stream')
        # Properly encode filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(file['file_name'])
        response.headers.set('Content-Disposition', f'attachment; filename="{safe_filename}"')
        return response
    return 'File not found', 404

@app.route('/receiving1/folder/<int:folder_id>/preview/<int:file_id>')
def preview_folder_file(folder_id, file_id):
    if session.get('role') not in ['admin', 'receiving1']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM folder_files WHERE id = %s AND folder_id = %s", (file_id, folder_id))
    file = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if file and file['file_blob']:
        filename = file['file_name']
        # Guess content type
        if filename.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        elif filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        else:
            content_type = file['file_type'] or 'application/octet-stream'
        
        response = make_response(file['file_blob'])
        response.headers.set('Content-Type', content_type)
        
        # Properly encode filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(filename)
        response.headers.set('Content-Disposition', f'inline; filename="{safe_filename}"')
        
        return response
    return 'File not found', 404

@app.route('/create_user', methods=['GET', 'POST'])
def create_user():
    success = None
    error = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        role = request.form['role']
        # Accept 'releasing' as a valid role
        allowed_roles = ['admin', 'receiving1', 'receiving2', 'docs', 'releasing']
        if role not in allowed_roles:
            error = f"Invalid role selected."
        else:
            conn = get_db_connection()
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            existing_user = cursor.fetchone()
            if existing_user:
                error = f"Username '{username}' already exists. Please choose another."
            else:
                password_hash = generate_password_hash(password)
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO users (username, password_hash, role)
                    VALUES (%s, %s, %s)
                """, (username, password_hash, role))
                conn.commit()
                success = f"User '{username}' created successfully!"
            cursor.close()
            conn.close()
        if not error:
            return redirect(url_for('manage_users', success=1))
    return render_template('admin/create_user.html', success=success, error=error)

@app.route('/receiving2/add_email_docs', methods=['GET', 'POST'])
def receiving2_add_email_docs():
    if session.get('role') not in ['admin', 'receiving2']:
        return redirect(url_for('login'))
    import datetime
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    if request.method == 'POST':
        try:
            date_received = request.form['date_received']
            time_received = request.form['time_received']
            control_no = request.form['control_no']
            source = request.form['source']
            particulars = request.form['particulars']
            forwarded_to = request.form['forwarded_to']
            document_file = request.files.get('document_file')
            document_file_name = document_file.filename if document_file else ''
            document_blob = document_file.read() if document_file else None
            
            # Handle additional attachment
            additional_attachment = request.files.get('additional_attachment')
            additional_attachment_name = additional_attachment.filename if additional_attachment else ''
            additional_attachment_blob = additional_attachment.read() if additional_attachment else None
            
            created_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Handle purpose/action checkboxes
            purpose_actions = request.form.getlist('purpose')
            purpose_action_str = ', '.join(purpose_actions) if purpose_actions else ''
            
            cursor.execute("""
                INSERT INTO other_documents (date_received, time_received, control_no, source, particulars, forwarded_to, document_file, document_blob, created_at, purpose_action, attachment_file, attachment_blob)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (date_received, time_received, control_no, source, particulars, forwarded_to, document_file_name, document_blob, created_at, purpose_action_str, additional_attachment_name, additional_attachment_blob))
            conn.commit()
            cursor.close()
            conn.close()
            return redirect(url_for('receiving2_add_email_docs', success='1'))
        except Exception as e:
            conn.rollback()
            cursor.close()
            conn.close()
            print(f"Error adding document: {e}")
            return redirect(url_for('receiving2_add_email_docs', error='1'))
    
    try:
        cursor.execute("SELECT id, date_received, time_received, control_no, source, particulars, received_by, forwarded_to, document_file, created_at, purpose_action, attachment_file FROM other_documents ORDER BY created_at DESC")
        email_documents = cursor.fetchall()
    except Exception as e:
        print(f"Error fetching documents: {e}")
        email_documents = []
    
    cursor.close()
    conn.close()
    success = request.args.get('success')
    error = request.args.get('error')
    return render_template('receiving2/add_email_docs.html', email_documents=email_documents, success=success, error=error)

@app.route('/receiving2/outgoing_docs')
def receiving2_outgoing_docs():
    if session.get('role') not in ['admin', 'receiving2']:
        return redirect(url_for('login'))
    
    # Pagination parameters
    page = request.args.get('page', 1, type=int)
    per_page = 20  # Number of documents per page
    offset = (page - 1) * per_page
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get total outgoing documents from accepted_documents table
    cursor.execute("SELECT COUNT(*) AS total FROM accepted_documents")
    total_outgoing_docs = cursor.fetchone()['total']
    
    # Get today's outgoing documents from accepted_documents table
    cursor.execute("SELECT COUNT(*) AS today FROM accepted_documents WHERE DATE(date_accepted) = CURDATE()")
    today_outgoing_docs = cursor.fetchone()['today']
    
    # Get total accepted documents from accepted_documents table
    cursor.execute("SELECT COUNT(*) AS accepted FROM accepted_documents")
    accepted_docs = cursor.fetchone()['accepted']
    
    # Get total other documents
    cursor.execute("SELECT COUNT(*) AS total_other FROM other_documents")
    total_other_docs = cursor.fetchone()['total_other']
    
    # Get paginated accepted documents from the dedicated accepted_documents table - exclude document_blob
    cursor.execute("""
        SELECT id, original_receiving1_id, date_received, time_received, control_no, source, particulars, received_by, forwarded_to, document_file, date_accepted, time_accepted, accepted_by, purposes, remarks, attachment_file, created_at FROM accepted_documents 
        ORDER BY date_accepted DESC, time_accepted DESC, created_at DESC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    outgoing_documents = cursor.fetchall()
    
    # Get total count of accepted documents for pagination
    cursor.execute("SELECT COUNT(*) AS total FROM accepted_documents")
    total_accepted_count = cursor.fetchone()['total']
    
    # Get paginated other documents - exclude document_blob
    cursor.execute("""
        SELECT id, date_received, time_received, control_no, source, particulars, received_by, forwarded_to, document_file, created_at, purpose_action, attachment_file FROM other_documents 
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """, (per_page, offset))
    other_documents = cursor.fetchall()
    
    # Get total count of other documents for pagination
    cursor.execute("SELECT COUNT(*) AS total FROM other_documents")
    total_other_count = cursor.fetchone()['total']
    
    cursor.close()
    conn.close()
    
    # Calculate pagination info
    total_documents = total_accepted_count + total_other_count
    total_pages = (total_documents + per_page - 1) // per_page
    
    return render_template('receiving2/outgoing_document.html', 
                         outgoing_documents=outgoing_documents,
                         other_documents=other_documents,
                         total_outgoing_docs=total_outgoing_docs,
                         today_outgoing_docs=today_outgoing_docs,
                         accepted_docs=accepted_docs,
                         total_other_docs=total_other_docs,
                         active_page='receiving2_outgoing_document',
                         # Pagination variables
                         page=page,
                         per_page=per_page,
                         total_pages=total_pages,
                         total_documents=total_documents,
                         has_prev=page > 1,
                         has_next=page < total_pages)

@app.route('/receiving2download_email_doc/<int:doc_id>')
def download_email_doc(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT document_file, document_blob FROM other_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['document_blob']:
        response = make_response(doc['document_blob'])
        response.headers.set('Content-Type', 'application/octet-stream')
        # Properly encode filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(doc['document_file'])
        response.headers.set('Content-Disposition', f'attachment; filename="{safe_filename}"')
        return response
    return 'File not found', 404

@app.route('/receiving2/preview_email_doc/<int:doc_id>')
def preview_email_doc(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT document_file, document_blob FROM other_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['document_blob']:
        filename = doc['document_file']
        # Guess content type
        if filename.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        elif filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        else:
            content_type = 'application/octet-stream'
        response = make_response(doc['document_blob'])
        response.headers.set('Content-Type', content_type)
        
        # Properly encode filename for Content-Disposition header to avoid multiple headers issue
        import urllib.parse
        safe_filename = urllib.parse.quote(filename)
        response.headers.set('Content-Disposition', f'inline; filename="{safe_filename}"')
        
        return response
    return 'File not found', 404

@app.route('/receiving2/download_email_doc_attachment/<int:doc_id>')
def download_email_doc_attachment(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT attachment_file, attachment_blob FROM other_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['attachment_blob']:
        response = make_response(doc['attachment_blob'])
        response.headers.set('Content-Type', 'application/octet-stream')
        # Properly encode filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(doc['attachment_file'])
        response.headers.set('Content-Disposition', f'attachment; filename="{safe_filename}"')
        return response
    return 'File not found', 404

@app.route('/receiving2/preview_email_doc_attachment/<int:doc_id>')
def preview_email_doc_attachment(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT attachment_file, attachment_blob FROM other_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['attachment_blob']:
        filename = doc['attachment_file']
        # Guess content type
        if filename and filename.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        elif filename and filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif filename and filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif filename and filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        else:
            content_type = 'application/octet-stream'
        response = make_response(doc['attachment_blob'])
        response.headers.set('Content-Type', content_type)
        
        # Properly encode filename for Content-Disposition header to avoid multiple headers issue
        import urllib.parse
        safe_filename = urllib.parse.quote(filename)
        response.headers.set('Content-Disposition', f'inline; filename="{safe_filename}"')
        
        return response
    return 'File not found', 404

@app.route('/receiving2/download/<int:doc_id>')
def download_receiving2_file(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT document_file, document_blob FROM receiving2_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['document_blob']:
        response = make_response(doc['document_blob'])
        response.headers.set('Content-Type', 'application/octet-stream')
        # Properly encode filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(doc['document_file'])
        response.headers.set('Content-Disposition', f'attachment; filename="{safe_filename}"')
        return response
    return 'File not found', 404

@app.route('/receiving2/preview/<int:doc_id>')
def preview_receiving2_file(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT document_file, document_blob FROM receiving2_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not doc:
        return 'Document not found', 404
    
    if not doc['document_blob']:
        return 'Document file is empty or corrupted', 404
    
    filename = doc['document_file']
    if not filename:
        return 'Document filename is missing', 404
    
    # Guess content type
    if filename.lower().endswith('.pdf'):
        content_type = 'application/pdf'
    elif filename.lower().endswith(('.jpg', '.jpeg')):
        content_type = 'image/jpeg'
    elif filename.lower().endswith('.png'):
        content_type = 'image/png'
    elif filename.lower().endswith('.gif'):
        content_type = 'image/gif'
    elif filename.lower().endswith(('.doc', '.docx')):
        content_type = 'application/msword'
    elif filename.lower().endswith('.txt'):
        content_type = 'text/plain'
    else:
        content_type = 'application/octet-stream'
    
    response = make_response(doc['document_blob'])
    response.headers.set('Content-Type', content_type)
    
    # Properly encode filename for Content-Disposition header
    import urllib.parse
    safe_filename = urllib.parse.quote(filename)
    response.headers.set('Content-Disposition', f'inline; filename="{safe_filename}"')
    
    # Add cache control headers to prevent caching issues
    response.headers.set('Cache-Control', 'no-cache, no-store, must-revalidate')
    response.headers.set('Pragma', 'no-cache')
    response.headers.set('Expires', '0')
    
    return response

@app.route('/receiving2/download_attachment/<int:receiving2_id>')
def download_receiving2_attachment(receiving2_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT attachment_file, attachment_blob FROM receiving2_documents WHERE id = %s", (receiving2_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['attachment_blob']:
        response = make_response(doc['attachment_blob'])
        response.headers.set('Content-Type', 'application/octet-stream')
        # Properly encode filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(doc['attachment_file'])
        response.headers.set('Content-Disposition', f'attachment; filename="{safe_filename}"')
        return response
    return 'File not found', 404

@app.route('/receiving2/preview_attachment/<int:receiving2_id>')
def preview_receiving2_attachment(receiving2_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT attachment_file, attachment_blob FROM receiving2_documents WHERE id = %s", (receiving2_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['attachment_blob']:
        filename = doc['attachment_file']
        # Guess content type
        if filename and filename.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        elif filename and filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif filename and filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif filename and filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        else:
            content_type = 'application/octet-stream'
        response = make_response(doc['attachment_blob'])
        response.headers.set('Content-Type', content_type)
        
        # Properly encode filename for Content-Disposition header to avoid multiple headers issue
        import urllib.parse
        safe_filename = urllib.parse.quote(filename)
        response.headers.set('Content-Disposition', f'inline; filename="{safe_filename}"')
        
        return response
    return 'File not found', 404

@app.route('/receiving2/download_accepted_document/<int:doc_id>')
def download_accepted_document(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT document_file, document_blob FROM accepted_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['document_blob']:
        response = make_response(doc['document_blob'])
        response.headers.set('Content-Type', 'application/octet-stream')
        # Properly encode filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(doc['document_file'])
        response.headers.set('Content-Disposition', f'attachment; filename="{safe_filename}"')
        return response
    return 'File not found', 404

@app.route('/receiving2/preview_accepted_document/<int:doc_id>')
def preview_accepted_document(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT document_file, document_blob FROM accepted_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['document_blob']:
        filename = doc['document_file']
        # Guess content type
        if filename and filename.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        elif filename and filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif filename and filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif filename and filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        else:
            content_type = 'application/octet-stream'
        response = make_response(doc['document_blob'])
        response.headers.set('Content-Type', content_type)
        
        # Properly encode filename for Content-Disposition header to avoid multiple headers issue
        import urllib.parse
        safe_filename = urllib.parse.quote(filename)
        response.headers.set('Content-Disposition', f'inline; filename="{safe_filename}"')
        
        return response
    return 'File not found', 404

@app.route('/receiving2/download_accepted_attachment/<int:doc_id>')
def download_accepted_attachment(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT attachment_file, attachment_blob FROM accepted_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['attachment_blob']:
        response = make_response(doc['attachment_blob'])
        response.headers.set('Content-Type', 'application/octet-stream')
        # Properly encode filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(doc['attachment_file'])
        response.headers.set('Content-Disposition', f'attachment; filename="{safe_filename}"')
        return response
    return 'File not found', 404

@app.route('/receiving2/preview_accepted_attachment/<int:doc_id>')
def preview_accepted_attachment(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT attachment_file, attachment_blob FROM accepted_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['attachment_blob']:
        filename = doc['attachment_file']
        # Guess content type
        if filename and filename.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        elif filename and filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif filename and filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif filename and filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        else:
            content_type = 'application/octet-stream'
        response = make_response(doc['attachment_blob'])
        response.headers.set('Content-Type', content_type)
        
        # Properly encode filename for Content-Disposition header to avoid multiple headers issue
        import urllib.parse
        safe_filename = urllib.parse.quote(filename)
        response.headers.set('Content-Disposition', f'inline; filename="{safe_filename}"')
        
        return response
    return 'File not found', 404

@app.route('/releasing/outgoing/download/<int:doc_id>')
def download_outgoing_file(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT document_file, document_blob FROM outgoing_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['document_blob']:
        response = make_response(doc['document_blob'])
        response.headers.set('Content-Type', 'application/octet-stream')
        # Properly encode filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(doc['document_file'])
        response.headers.set('Content-Disposition', f'attachment; filename="{safe_filename}"')
        return response
    return 'File not found', 404

@app.route('/releasing/outgoing/preview/<int:doc_id>')
def preview_outgoing_file(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT document_file, document_blob FROM outgoing_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['document_blob']:
        filename = doc['document_file']
        if filename and filename.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        elif filename and filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif filename and filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif filename and filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        else:
            content_type = 'application/octet-stream'
        response = make_response(doc['document_blob'])
        response.headers.set('Content-Type', content_type)
        
        # Properly encode filename for Content-Disposition header to avoid multiple headers issue
        import urllib.parse
        safe_filename = urllib.parse.quote(filename)
        response.headers.set('Content-Disposition', f'inline; filename="{safe_filename}"')
        
        return response
    return 'File not found', 404

@app.route('/releasing/outgoing/preview_page/<int:doc_id>')
def outgoing_preview_page(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT id, date_sent, time_sent, control_no, source, particulars, forwarded_to, document_file, created_at FROM outgoing_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if not doc:
        return 'Document not found', 404
    return render_template('releasing/outgoing_preview.html', doc=doc)

@app.route('/releasing/outgoing/edit/<int:doc_id>', methods=['GET', 'POST'])
def edit_outgoing_document(doc_id):
    if session.get('role') not in ['admin', 'releasing']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        try:
            date_sent = request.form['date_sent']
            time_sent = request.form['time_sent']
            control_no = request.form['control_no']
            source = request.form['source']
            particulars = request.form['particulars']
            forwarded_to = request.form['forwarded_to']
            
            # Handle file upload if new file is provided
            document_file = request.files.get('document_file')
            if document_file and document_file.filename:
                document_file_name = document_file.filename
                document_blob = document_file.read()
                cursor.execute("""
                    UPDATE outgoing_documents 
                    SET date_sent = %s, time_sent = %s, control_no = %s, source = %s, 
                        particulars = %s, forwarded_to = %s, document_file = %s, document_blob = %s
                    WHERE id = %s
                """, (date_sent, time_sent, control_no, source, particulars, 
                      forwarded_to, document_file_name, document_blob, doc_id))
            else:
                cursor.execute("""
                    UPDATE outgoing_documents 
                    SET date_sent = %s, time_sent = %s, control_no = %s, source = %s, 
                        particulars = %s, forwarded_to = %s
                    WHERE id = %s
                """, (date_sent, time_sent, control_no, source, particulars, 
                      forwarded_to, doc_id))
            
            conn.commit()
            cursor.close()
            conn.close()
            return jsonify({'success': True, 'message': 'Document updated successfully!'})
            
        except Exception as e:
            conn.rollback()
            cursor.close()
            conn.close()
            return jsonify({'success': False, 'message': f'Error updating document: {str(e)}'})
    
    # GET request - fetch document data - exclude document_blob
    cursor.execute("SELECT id, date_sent, time_sent, control_no, source, particulars, forwarded_to, document_file, created_at FROM outgoing_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if not doc:
        return jsonify({'success': False, 'message': 'Document not found'})
    
    return jsonify({
        'success': True,
        'document': {
            'id': doc['id'],
            'date_sent': str(doc['date_sent']),
            'time_sent': str(doc['time_sent']) if doc['time_sent'] else '',
            'control_no': doc['control_no'],
            'source': doc['source'],
            'particulars': doc['particulars'] if doc['particulars'] else '',
            'forwarded_to': doc['forwarded_to'] if doc['forwarded_to'] else '',
            'document_file': doc['document_file'] if doc['document_file'] else ''
        }
    })

# Releasing Document Folder Routes
@app.route('/releasing/outgoing_folder', methods=['GET', 'POST'])
def releasing_outgoing_folder():
    if session.get('role') not in ['admin', 'releasing']:
        return redirect(url_for('login'))
    
    success = None
    error = None
    
    # Check for session-based success message
    if session.get('upload_success'):
        success = True
        session.pop('upload_success', None)
    
    if session.get('edit_success'):
        success = True
        session.pop('edit_success', None)  # Clear the session flag
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    if request.method == 'POST':
        try:
            folder_name = request.form['folder_name']
            folder_description = request.form.get('folder_description', '')
            document_files = request.files.getlist('document_files')
            
            if not folder_name or not document_files or all(f.filename == '' for f in document_files):
                error = "Please provide a folder name and select at least one file."
            else:
                # Insert folder
                cursor.execute("""
                    INSERT INTO releasing_document_folders (folder_name, folder_description, created_by)
                    VALUES (%s, %s, %s)
                """, (folder_name, folder_description, session.get('username')))
                
                folder_id = cursor.lastrowid
                file_count = 0
                
                # Insert files
                for file in document_files:
                    if file.filename:
                        file_data = file.read()
                        cursor.execute("""
                            INSERT INTO releasing_folder_files (folder_id, file_name, file_type, file_size, file_data, uploaded_by)
                            VALUES (%s, %s, %s, %s, %s, %s)
                        """, (folder_id, file.filename, file.content_type, len(file_data), file_data, session.get('username')))
                        file_count += 1
                
                # Update file count
                cursor.execute("UPDATE releasing_document_folders SET file_count = %s WHERE id = %s", (file_count, folder_id))
                conn.commit()
                
                # Use session for success message
                session['upload_success'] = True
                return redirect(url_for('releasing_outgoing_folder'))
                
        except Exception as e:
            conn.rollback()
            error = f"Error uploading folder: {str(e)}"
        finally:
            cursor.close()
            conn.close()
    
    # Get folders with file counts
    cursor.execute("""
        SELECT f.*, COUNT(ff.id) as file_count 
        FROM releasing_document_folders f 
        LEFT JOIN releasing_folder_files ff ON f.id = ff.folder_id 
        GROUP BY f.id 
        ORDER BY f.created_at DESC
    """)
    folders = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('releasing/outgoing_folder.html', folders=folders, success=success, error=error, active_page='releasing_outgoing_folder')

@app.route('/releasing/folder/<int:folder_id>')
def releasing_view_folder_contents(folder_id):
    if session.get('role') not in ['admin', 'releasing']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Get folder info
    cursor.execute("SELECT * FROM releasing_document_folders WHERE id = %s", (folder_id,))
    folder = cursor.fetchone()
    
    if not folder:
        cursor.close()
        conn.close()
        return 'Folder not found', 404
    
    # Get files in folder
    cursor.execute("SELECT * FROM releasing_folder_files WHERE folder_id = %s ORDER BY uploaded_at DESC", (folder_id,))
    files = cursor.fetchall()
    cursor.close()
    conn.close()
    
    return render_template('releasing/folder_contents.html', folder=folder, files=files, active_page='releasing_outgoing_folder')

@app.route('/releasing/search_folders')
def releasing_search_folders():
    if session.get('role') not in ['admin', 'releasing']:
        return jsonify({'folders': [], 'files': []})
    
    search_term = request.args.get('q', '').strip()
    if not search_term:
        return jsonify({'folders': [], 'files': []})
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Split search terms for fuzzy search
    search_words = search_term.split()
    
    # Build folder search conditions
    folder_conditions = []
    folder_params = []
    
    # Original exact match for backward compatibility
    folder_conditions.append("(f.folder_name LIKE %s OR f.folder_description LIKE %s)")
    folder_params.extend([f'%{search_term}%', f'%{search_term}%'])
    
    # Fuzzy search: check if all words are present in folder name or description
    if len(search_words) > 1:
        folder_word_conditions = []
        for word in search_words:
            folder_word_conditions.append("(f.folder_name LIKE %s OR f.folder_description LIKE %s)")
            folder_params.extend([f'%{word}%', f'%{word}%'])
        folder_conditions.append(f"({' AND '.join(folder_word_conditions)})")
    
    # Search folders (select only non-blob columns, align with receiving1 response shape)
    folder_query = f"""
        SELECT 
            f.id,
            f.folder_name,
            f.folder_description,
            f.created_at,
            COUNT(ff.id) AS file_count
        FROM releasing_document_folders f 
        LEFT JOIN releasing_folder_files ff ON f.id = ff.folder_id 
        WHERE {' OR '.join(folder_conditions)}
        GROUP BY f.id, f.folder_name, f.folder_description, f.created_at
        ORDER BY f.created_at DESC
    """
    cursor.execute(folder_query, folder_params)
    folders = cursor.fetchall()
    
    # Build file search conditions
    file_conditions = []
    file_params = []
    
    # Original exact match for backward compatibility
    file_conditions.append("ff.file_name LIKE %s")
    file_params.append(f'%{search_term}%')
    
    # Fuzzy search: check if all words are present in filename
    if len(search_words) > 1:
        file_word_conditions = []
        for word in search_words:
            file_word_conditions.append("ff.file_name LIKE %s")
            file_params.append(f'%{word}%')
        file_conditions.append(f"({' AND '.join(file_word_conditions)})")
    
    # Search files (exclude LONGBLOB/file_data to keep JSON serializable)
    file_query = f"""
        SELECT 
            ff.id,
            ff.file_name,
            ff.file_type,
            ff.file_size,
            ff.uploaded_at,
            ff.uploaded_by,
            f.id AS folder_id,
            f.folder_name
        FROM releasing_folder_files ff
        JOIN releasing_document_folders f ON ff.folder_id = f.id
        WHERE {' OR '.join(file_conditions)}
        ORDER BY ff.uploaded_at DESC
    """
    cursor.execute(file_query, file_params)
    files = cursor.fetchall()
    
    cursor.close()
    conn.close()
    
    return jsonify({'folders': folders, 'files': files})

@app.route('/releasing/folder/<int:folder_id>/download/<int:file_id>')
def releasing_download_folder_file(folder_id, file_id):
    if session.get('role') not in ['admin', 'releasing']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM releasing_folder_files WHERE id = %s AND folder_id = %s", (file_id, folder_id))
    file = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if file and file['file_data']:
        response = make_response(file['file_data'])
        response.headers.set('Content-Type', file['file_type'] or 'application/octet-stream')
        
        # Properly encode filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(file['file_name'])
        response.headers.set('Content-Disposition', f'attachment; filename="{safe_filename}"')
        
        return response
    return 'File not found', 404

@app.route('/releasing/folder/<int:folder_id>/preview/<int:file_id>')
def releasing_preview_folder_file(folder_id, file_id):
    if session.get('role') not in ['admin', 'releasing']:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM releasing_folder_files WHERE id = %s AND folder_id = %s", (file_id, folder_id))
    file = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if file and file['file_data']:
        filename = file['file_name']
        # Guess content type
        if filename.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        elif filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        else:
            content_type = file['file_type'] or 'application/octet-stream'
        
        response = make_response(file['file_data'])
        response.headers.set('Content-Type', content_type)
        
        # Properly encode filename for Content-Disposition header
        import urllib.parse
        safe_filename = urllib.parse.quote(filename)
        response.headers.set('Content-Disposition', f'inline; filename="{safe_filename}"')
        
        return response
    return 'File not found', 404

@app.route('/docs/special_permit/preview/<int:doc_id>')
def preview_special_permit_file(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT document_file, document_blob FROM special_permit_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['document_blob']:
        filename = doc['document_file']
        if filename and filename.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        elif filename and filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif filename and filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif filename and filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        else:
            content_type = 'application/octet-stream'
        response = make_response(doc['document_blob'])
        response.headers.set('Content-Type', content_type)
        
        # Properly encode filename for Content-Disposition header to avoid multiple headers issue
        import urllib.parse
        safe_filename = urllib.parse.quote(filename)
        response.headers.set('Content-Disposition', f'inline; filename="{safe_filename}"')
        
        return response
    return 'File not found', 404

@app.route('/docs/travel/preview/<int:doc_id>')
def preview_travel_file(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT document_file, document_blob FROM travel_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['document_blob']:
        filename = doc['document_file']
        if filename and filename.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        elif filename and filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif filename and filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif filename and filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        else:
            content_type = 'application/octet-stream'
        response = make_response(doc['document_blob'])
        response.headers.set('Content-Type', content_type)
        
        # Properly encode filename for Content-Disposition header to avoid multiple headers issue
        import urllib.parse
        safe_filename = urllib.parse.quote(filename)
        response.headers.set('Content-Disposition', f'inline; filename="{safe_filename}"')
        
        return response
    return 'File not found', 404

@app.route('/docs/application_leave/preview/<int:doc_id>')
def preview_application_leave_file(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT document_file, document_blob FROM application_leave_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    cursor.close()
    conn.close()
    if doc and doc['document_blob']:
        filename = doc['document_file']
        if filename and filename.lower().endswith('.pdf'):
            content_type = 'application/pdf'
        elif filename and filename.lower().endswith(('.jpg', '.jpeg')):
            content_type = 'image/jpeg'
        elif filename and filename.lower().endswith('.png'):
            content_type = 'image/png'
        elif filename and filename.lower().endswith('.gif'):
            content_type = 'image/gif'
        else:
            content_type = 'application/octet-stream'
        response = make_response(doc['document_blob'])
        response.headers.set('Content-Type', content_type)
        
        # Properly encode filename for Content-Disposition header to avoid multiple headers issue
        import urllib.parse
        safe_filename = urllib.parse.quote(filename)
        response.headers.set('Content-Disposition', f'inline; filename="{safe_filename}"')
        
        return response
    return 'File not found', 404

@app.route('/receiving2/rts/accept/<int:doc_id>', methods=['GET', 'POST'])
def receiving2_accept_rts(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Fetch the document from Receiving 1
    cursor.execute("SELECT * FROM receiving1_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    if not doc:
        cursor.close()
        conn.close()
        if request.args.get('modal') == '1':
            return jsonify({'error': 'Document not found'}), 404
        return 'Document not found', 404
    if request.method == 'POST':
        # Get editable control_no and other fields
        control_no = request.form['control_no']
        received_by = request.form.get('received_by', doc['received_by'])
        forwarded_to = request.form.get('forwarded_to', doc['forwarded_to'])
        edit_reason = request.form.get('edit_reason', '')
        edited_by = session.get('username', 'unknown')
        created_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        # New fields
        purposes = request.form.getlist('purpose')
        purposes_str = ','.join(purposes)
        remarks = request.form.get('remarks', '')
        rts_date = request.form.get('date')
        attachment_file = None
        attachment_blob = None
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename:
                attachment_file = file.filename
                attachment_blob = file.read()
        cursor2 = conn.cursor()
        cursor2.execute("""
            INSERT INTO receiving2_documents (
                original_receiving1_id, date_received, time_received, control_no, source, particulars, received_by, forwarded_to, document_file, document_blob, created_at, edited_by, edit_reason, purposes, remarks, rts_date, attachment_file, attachment_blob
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            doc['id'], doc['date_received'], doc['time_received'], control_no, doc['source'], doc['particulars'], received_by, forwarded_to, doc['document_file'], doc['document_blob'], created_at, edited_by, edit_reason, purposes_str, remarks, rts_date, attachment_file, attachment_blob
        ))
        
        # Mark as accepted in receiving1_documents and store date/time accepted
        now = datetime.datetime.now()
        date_accepted = now.strftime('%Y-%m-%d')
        time_accepted = now.strftime('%H:%M:%S')
        
        # Also insert into accepted_documents table for outgoing docs
        cursor2.execute("""
            INSERT INTO accepted_documents (
                original_receiving1_id, date_received, time_received, control_no, source, particulars, received_by, forwarded_to, document_file, document_blob, date_accepted, time_accepted, accepted_by, purposes, remarks, attachment_file, attachment_blob
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            doc['id'], doc['date_received'], doc['time_received'], control_no, doc['source'], doc['particulars'], received_by, forwarded_to, doc['document_file'], doc['document_blob'], date_accepted, time_accepted, edited_by, purposes_str, remarks, attachment_file, attachment_blob
        ))
        
        cursor2.execute("UPDATE receiving1_documents SET accepted_by_receiving2 = 1, date_accepted = %s, time_accepted = %s WHERE id = %s", (date_accepted, time_accepted, doc['id']))
        conn.commit()
        cursor2.close()
        # Do not delete from receiving1_documents; maintain the data
        cursor.close()
        conn.close()
        return redirect(url_for('receiving2_dashboard'))
    if request.args.get('modal') == '1':
        # Return JSON for modal
        cursor.close()
        conn.close()
        return jsonify({
            'control_no': doc['control_no'],
            'received_by': doc['received_by'],
            'forwarded_to': doc['forwarded_to'],
            'date_received': str(doc['date_received']),
            'time_received': str(doc['time_received']),
            'source': doc['source'],
            'particulars': doc['particulars'],
            'document_file': doc['document_file']
        })
    cursor.close()
    conn.close()
    return render_template('receiving2/accept_rts.html', doc=doc)

@app.route('/receiving2/rts/accept/email/<int:doc_id>', methods=['GET', 'POST'])
def receiving2_accept_email_rts(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Fetch the document from email_documents
    cursor.execute("SELECT * FROM other_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    if not doc:
        cursor.close()
        conn.close()
        if request.args.get('modal') == '1':
            return jsonify({'error': 'Document not found'}), 404
        return 'Document not found', 404
    if request.method == 'POST':
        control_no = request.form['control_no']
        received_by = doc['received_by']
        forwarded_to = request.form.get('forwarded_to', doc['forwarded_to'])
        edit_reason = request.form.get('edit_reason', '')
        edited_by = session.get('username', 'unknown')
        created_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        purposes = request.form.getlist('purpose')
        purposes_str = ','.join(purposes)
        remarks = request.form.get('remarks', '')
        rts_date = request.form.get('date')
        attachment_file = None
        attachment_blob = None
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename:
                attachment_file = file.filename
                attachment_blob = file.read()
        cursor2 = conn.cursor()
        cursor2.execute("""
            INSERT INTO receiving2_documents (
                original_receiving1_id, date_received, time_received, control_no, source, particulars, received_by, forwarded_to, document_file, document_blob, created_at, edited_by, edit_reason, purposes, remarks, rts_date, attachment_file, attachment_blob
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            doc['id'], doc['date_received'], doc['time_received'], control_no, doc['source'], doc['particulars'], received_by, forwarded_to, doc['document_file'], doc['document_blob'], created_at, edited_by, edit_reason, purposes_str, remarks, rts_date, attachment_file, attachment_blob
        ))
        conn.commit()
        cursor2.close()
        cursor.close()
        conn.close()
        return redirect(url_for('receiving2_rts'))
    if request.args.get('modal') == '1':
        cursor.close()
        conn.close()
        return jsonify({
            'control_no': doc['control_no'],
            'forwarded_to': doc['forwarded_to'],
            'date_received': str(doc['date_received']),
            'time_received': str(doc['time_received']),
            'source': doc['source'],
            'particulars': doc['particulars'],
            'document_file': doc['document_file']
        })
    cursor.close()
    conn.close()
    return render_template('receiving2/accept_rts.html', doc=doc)

@app.route('/receiving2/rts/accept/other/<int:doc_id>', methods=['GET', 'POST'])
def receiving2_accept_other_rts(doc_id):
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Fetch the document from other_documents
    cursor.execute("SELECT * FROM other_documents WHERE id = %s", (doc_id,))
    doc = cursor.fetchone()
    if not doc:
        cursor.close()
        conn.close()
        if request.args.get('modal') == '1':
            return jsonify({'error': 'Document not found'}), 404
        return 'Document not found', 404
    if request.method == 'POST':
        control_no = request.form['control_no']
        received_by = doc['received_by']
        forwarded_to = request.form.get('forwarded_to', doc['forwarded_to'])
        edit_reason = request.form.get('edit_reason', '')
        edited_by = session.get('username', 'unknown')
        created_at = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        purposes = request.form.getlist('purpose')
        purposes_str = ','.join(purposes)
        remarks = request.form.get('remarks', '')
        rts_date = request.form.get('date')
        attachment_file = None
        attachment_blob = None
        if 'attachment' in request.files:
            file = request.files['attachment']
            if file and file.filename:
                attachment_file = file.filename
                attachment_blob = file.read()
        cursor2 = conn.cursor()
        cursor2.execute("""
            INSERT INTO receiving2_documents (
                original_receiving1_id, date_received, time_received, control_no, source, particulars, received_by, forwarded_to, document_file, document_blob, created_at, edited_by, edit_reason, purposes, remarks, rts_date, attachment_file, attachment_blob
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            doc['id'], doc['date_received'], doc['time_received'], control_no, doc['source'], doc['particulars'], received_by, forwarded_to, doc['document_file'], doc['document_blob'], created_at, edited_by, edit_reason, purposes_str, remarks, rts_date, attachment_file, attachment_blob
        ))
        conn.commit()
        cursor2.close()
        cursor.close()
        conn.close()
        return redirect(url_for('receiving2_rts'))
    if request.args.get('modal') == '1':
        cursor.close()
        conn.close()
        # For other docs, do not prefill the form fields
        return jsonify({
            'control_no': '',
            'forwarded_to': '',
            'date_received': '',
            'time_received': '',
            'source': '',
            'particulars': '',
            'document_file': ''
        })
    cursor.close()
    conn.close()
    return render_template('receiving2/accept_rts.html', doc=doc)

@app.route('/receiving2/update_accepted_document', methods=['POST'])
def update_accepted_document():
    if session.get('role') not in ['admin', 'receiving2']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        doc_id = request.form.get('doc_id')
        
        if not doc_id:
            return jsonify({'success': False, 'message': 'Missing document ID'})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get form data
        date_received = request.form.get('date_received')
        time_received = request.form.get('time_received')
        control_no = request.form.get('control_no')
        source = request.form.get('source')
        particulars = request.form.get('particulars')
        forwarded_to = request.form.get('forwarded_to')
        
        # Handle purpose/action checkboxes
        purpose_actions = request.form.getlist('purpose')
        purposes_str = ', '.join(purpose_actions) if purpose_actions else ''
        remarks = request.form.get('remarks', '')
        
        # Handle file uploads
        document_file = request.files.get('document_file')
        additional_attachment = request.files.get('additional_attachment')
        
        # Build update query
        update_fields = []
        update_values = []
        
        if date_received:
            update_fields.append("date_received = %s")
            update_values.append(date_received)
        
        if time_received:
            update_fields.append("time_received = %s")
            update_values.append(time_received)
        
        if control_no is not None:
            update_fields.append("control_no = %s")
            update_values.append(control_no)
        
        if source:
            update_fields.append("source = %s")
            update_values.append(source)
        
        if particulars:
            update_fields.append("particulars = %s")
            update_values.append(particulars)
        
        if forwarded_to is not None:
            update_fields.append("forwarded_to = %s")
            update_values.append(forwarded_to)
        
        if purposes_str:
            update_fields.append("purposes = %s")
            update_values.append(purposes_str)
        
        if remarks:
            update_fields.append("remarks = %s")
            update_values.append(remarks)
        
        # Handle document file update
        if document_file and document_file.filename:
            document_file_name = document_file.filename
            document_blob = document_file.read()
            update_fields.append("document_file = %s")
            update_fields.append("document_blob = %s")
            update_values.extend([document_file_name, document_blob])
        
        # Handle attachment file update
        if additional_attachment and additional_attachment.filename:
            attachment_file_name = additional_attachment.filename
            attachment_blob = additional_attachment.read()
            update_fields.append("attachment_file = %s")
            update_fields.append("attachment_blob = %s")
            update_values.extend([attachment_file_name, attachment_blob])
        
        if update_fields:
            update_values.append(doc_id)
            query = f"UPDATE accepted_documents SET {', '.join(update_fields)} WHERE id = %s"
            cursor.execute(query, update_values)
            conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Document updated successfully'})
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        return jsonify({'success': False, 'message': f'Error updating document: {str(e)}'})

@app.route('/receiving2/update_other_document', methods=['POST'])
def update_other_document():
    if session.get('role') not in ['admin', 'receiving2']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        doc_id = request.form.get('doc_id')
        
        if not doc_id:
            return jsonify({'success': False, 'message': 'Missing document ID'})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get form data
        date_received = request.form.get('date_received')
        time_received = request.form.get('time_received')
        control_no = request.form.get('control_no')
        source = request.form.get('source')
        particulars = request.form.get('particulars')
        forwarded_to = request.form.get('forwarded_to')
        
        # Handle purpose/action checkboxes
        purpose_actions = request.form.getlist('purpose')
        purpose_action_str = ', '.join(purpose_actions) if purpose_actions else ''
        
        # Handle file uploads
        document_file = request.files.get('document_file')
        additional_attachment = request.files.get('additional_attachment')
        
        # Build update query
        update_fields = []
        update_values = []
        
        if date_received:
            update_fields.append("date_received = %s")
            update_values.append(date_received)
        
        if time_received:
            update_fields.append("time_received = %s")
            update_values.append(time_received)
        
        if control_no is not None:
            update_fields.append("control_no = %s")
            update_values.append(control_no)
        
        if source:
            update_fields.append("source = %s")
            update_values.append(source)
        
        if particulars:
            update_fields.append("particulars = %s")
            update_values.append(particulars)
        
        if forwarded_to is not None:
            update_fields.append("forwarded_to = %s")
            update_values.append(forwarded_to)
        
        if purpose_action_str:
            update_fields.append("purpose_action = %s")
            update_values.append(purpose_action_str)
        
        # Handle document file update
        if document_file and document_file.filename:
            document_file_name = document_file.filename
            document_blob = document_file.read()
            update_fields.append("document_file = %s")
            update_fields.append("document_blob = %s")
            update_values.extend([document_file_name, document_blob])
        
        # Handle attachment file update
        if additional_attachment and additional_attachment.filename:
            attachment_file_name = additional_attachment.filename
            attachment_blob = additional_attachment.read()
            update_fields.append("attachment_file = %s")
            update_fields.append("attachment_blob = %s")
            update_values.extend([attachment_file_name, attachment_blob])
        
        if update_fields:
            update_values.append(doc_id)
            query = f"UPDATE other_documents SET {', '.join(update_fields)} WHERE id = %s"
            cursor.execute(query, update_values)
            conn.commit()
        
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Document updated successfully'})
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        return jsonify({'success': False, 'message': f'Error updating document: {str(e)}'})

@app.route('/receiving2/update_purpose_action', methods=['POST'])
def update_purpose_action():
    if session.get('role') not in ['admin', 'receiving2']:
        return jsonify({'success': False, 'message': 'Unauthorized'}), 401
    
    try:
        doc_id = request.form.get('doc_id')
        doc_type = request.form.get('doc_type')
        
        if not doc_id or not doc_type:
            return jsonify({'success': False, 'message': 'Missing required parameters'})
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if doc_type == 'accepted':
            # Update accepted_documents table
            purposes = request.form.get('purposes', '')
            remarks = request.form.get('remarks', '')
            
            cursor.execute("""
                UPDATE accepted_documents 
                SET purposes = %s, remarks = %s 
                WHERE id = %s
            """, (purposes, remarks, doc_id))
            
        elif doc_type == 'other':
            # Update other_documents table
            purpose_action = request.form.get('purpose_action', '')
            
            cursor.execute("""
                UPDATE other_documents 
                SET purpose_action = %s 
                WHERE id = %s
            """, (purpose_action, doc_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Purpose and action updated successfully'})
        
    except Exception as e:
        if 'conn' in locals():
            conn.rollback()
            cursor.close()
            conn.close()
        return jsonify({'success': False, 'message': f'Error updating purpose and action: {str(e)}'})

@app.route('/admin/reports')
def admin_reports():
    if session.get('role') != 'admin':
        return redirect(url_for('login'))
    
    # Get filter parameters
    record_type = request.args.get('record_type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Initialize records list
    all_records = []
    
    # Get Receiving 1 documents - exclude document_blob
    if not record_type or record_type == 'receiving1':
        receiving1_query = "SELECT id, date_received, time_received, control_no, source, particulars, received_by, document_receiver, forwarded_to, document_file, created_at, routed_to_receiving2, accepted_by_receiving2 FROM receiving1_documents WHERE 1=1"
        receiving1_params = []
        
        if date_from:
            receiving1_query += " AND date_received >= %s"
            receiving1_params.append(date_from)
        if date_to:
            receiving1_query += " AND date_received <= %s"
            receiving1_params.append(date_to)
        if search:
            receiving1_query += " AND (control_no LIKE %s OR source LIKE %s OR particulars LIKE %s)"
            search_param = f"%{search}%"
            receiving1_params.extend([search_param, search_param, search_param])
        
        receiving1_query += " ORDER BY date_received DESC, time_received DESC"
        
        cursor.execute(receiving1_query, receiving1_params)
        receiving1_docs = cursor.fetchall()
        
        for doc in receiving1_docs:
            all_records.append({
                'type': 'receiving1',
                'date': doc['date_received'],
                'control_no': doc['control_no'],
                'source': doc['source'],
                'particulars': doc['particulars'],
                'received_by': doc['received_by'],
                'document_file': doc['document_file'],
                'download_url': url_for('download_receiving1_file', doc_id=doc['id']),
                'preview_url': url_for('preview_receiving1_file', doc_id=doc['id'])
            })
    
    # Get Receiving 2 documents - exclude document_blob
    if not record_type or record_type == 'receiving2':
        receiving2_query = "SELECT id, original_receiving1_id, date_received, time_received, control_no, source, particulars, received_by, forwarded_to, document_file, created_at, edited_by, edit_reason, purposes, remarks, rts_date, attachment_file FROM receiving2_documents WHERE 1=1"
        receiving2_params = []
        
        if date_from:
            receiving2_query += " AND date_received >= %s"
            receiving2_params.append(date_from)
        if date_to:
            receiving2_query += " AND date_received <= %s"
            receiving2_params.append(date_to)
        if search:
            receiving2_query += " AND (control_no LIKE %s OR source LIKE %s OR particulars LIKE %s)"
            search_param = f"%{search}%"
            receiving2_params.extend([search_param, search_param, search_param])
        
        receiving2_query += " ORDER BY date_received DESC, time_received DESC"
        
        cursor.execute(receiving2_query, receiving2_params)
        receiving2_docs = cursor.fetchall()
        
        for doc in receiving2_docs:
            all_records.append({
                'type': 'receiving2',
                'date': doc['date_received'],
                'control_no': doc['control_no'],
                'source': doc['source'],
                'particulars': doc['particulars'],
                'received_by': doc['received_by'],
                'document_file': doc['document_file'],
                'download_url': url_for('download_receiving2_file', doc_id=doc['id']),
                'preview_url': url_for('preview_receiving2_file', doc_id=doc['id'])
            })
    
    # Get Releasing documents (outgoing_documents) - exclude document_blob
    if not record_type or record_type == 'releasing':
        releasing_query = "SELECT id, date_sent, time_sent, control_no, source, particulars, forwarded_to, document_file, created_at FROM outgoing_documents WHERE 1=1"
        releasing_params = []
        
        if date_from:
            releasing_query += " AND date_sent >= %s"
            releasing_params.append(date_from)
        if date_to:
            releasing_query += " AND date_sent <= %s"
            releasing_params.append(date_to)
        if search:
            releasing_query += " AND (control_no LIKE %s OR source LIKE %s OR particulars LIKE %s)"
            search_param = f"%{search}%"
            releasing_params.extend([search_param, search_param, search_param])
        
        releasing_query += " ORDER BY date_sent DESC, time_sent DESC"
        
        cursor.execute(releasing_query, releasing_params)
        releasing_docs = cursor.fetchall()
        
        for doc in releasing_docs:
            all_records.append({
                'type': 'releasing',
                'date': doc['date_sent'],
                'control_no': doc['control_no'],
                'source': doc['source'],
                'particulars': doc['particulars'],
                'received_by': doc['forwarded_to'],  # Using forwarded_to as received_by
                'document_file': doc['document_file'],
                'download_url': url_for('download_outgoing_file', doc_id=doc['id']),
                'preview_url': url_for('preview_outgoing_file', doc_id=doc['id'])
            })
    
    # Get Documentation files (from document_folders and folder_files)
    if not record_type or record_type == 'docs':
        try:
            docs_query = """
                SELECT ff.id, ff.folder_id, ff.file_name, ff.file_size, ff.file_type, ff.uploaded_at, ff.uploaded_by, df.folder_name, df.folder_description 
                FROM folder_files ff 
                JOIN document_folders df ON ff.folder_id = df.id 
                WHERE 1=1
            """
            docs_params = []
            
            if date_from:
                docs_query += " AND ff.uploaded_at >= %s"
                docs_params.append(f"{date_from} 00:00:00")
            if date_to:
                docs_query += " AND ff.uploaded_at <= %s"
                docs_params.append(f"{date_to} 23:59:59")
            if search:
                docs_query += " AND (ff.file_name LIKE %s OR df.folder_name LIKE %s OR df.folder_description LIKE %s)"
                search_param = f"%{search}%"
                docs_params.extend([search_param, search_param, search_param])
            
            docs_query += " ORDER BY ff.uploaded_at DESC"
            
            cursor.execute(docs_query, docs_params)
            docs_files = cursor.fetchall()
            
            for doc in docs_files:
                all_records.append({
                    'type': 'docs',
                    'date': doc['uploaded_at'].date() if doc['uploaded_at'] else None,
                    'control_no': f"FOLDER-{doc['folder_id']}",
                    'source': doc['folder_name'],
                    'particulars': doc['folder_description'] or f"File in {doc['folder_name']}",
                    'received_by': doc['uploaded_by'],
                    'document_file': doc['file_name'],
                    'download_url': url_for('docs_download_folder_file', folder_id=doc['folder_id'], file_id=doc['id']),
                    'preview_url': url_for('docs_preview_folder_file', folder_id=doc['folder_id'], file_id=doc['id'])
                })
        except Exception as e:
            # If docs tables don't exist, skip
            pass
    
    # Sort all records by date (newest first)
    all_records.sort(key=lambda x: x['date'], reverse=True)
    
    # Get total counts for stats
    cursor.execute("SELECT COUNT(*) as total FROM receiving1_documents")
    total_receiving1 = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM receiving2_documents")
    total_receiving2 = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) as total FROM outgoing_documents")
    total_releasing = cursor.fetchone()['total']
    
    try:
        cursor.execute("SELECT COUNT(*) as total FROM folder_files")
        total_docs = cursor.fetchone()['total']
    except:
        total_docs = 0
    
    cursor.close()
    conn.close()
    
    # Pagination
    total_records = len(all_records)
    total_pages = (total_records + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    records = all_records[start_idx:end_idx]
    
    return render_template('admin/admin_reports.html',
                         records=records,
                         total_records=total_records,
                         total_receiving1=total_receiving1,
                         total_receiving2=total_receiving2,
                         total_releasing=total_releasing,
                         total_docs=total_docs,
                         current_page=page,
                         total_pages=total_pages)

@app.route('/debug/document/<int:doc_id>')
def debug_document(doc_id):
    """Debug route to check document information"""
    if session.get('role') != 'admin':
        return 'Unauthorized', 401
    
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    # Check receiving1 documents
    cursor.execute("SELECT id, document_file, LENGTH(document_blob) as blob_size FROM receiving1_documents WHERE id = %s", (doc_id,))
    receiving1_doc = cursor.fetchone()
    
    # Check receiving2 documents
    cursor.execute("SELECT id, document_file, LENGTH(document_blob) as blob_size FROM receiving2_documents WHERE id = %s", (doc_id,))
    receiving2_doc = cursor.fetchone()
    
    cursor.close()
    conn.close()
    
    result = {
        'doc_id': doc_id,
        'receiving1_document': receiving1_doc,
        'receiving2_document': receiving2_doc
    }
    
    return jsonify(result)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)