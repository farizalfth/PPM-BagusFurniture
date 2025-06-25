from flask import Flask, render_template, request, redirect, jsonify, flash, session, url_for, abort
from flask_mysqldb import MySQL
from functools import wraps

app = Flask(__name__)
app.secret_key = 'Bagus Furniture'

# Konfigurasi database
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root' 
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'web1'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'

mysql = MySQL(app)

# PENTING: Membuat variabel 'footer_content' tersedia di SEMUA template
@app.context_processor
def inject_global_content():
    try:
        cur = mysql.connection.cursor()
        cur.execute("SELECT page_value FROM content WHERE page_key = 'footer_content'")
        footer_content = cur.fetchone()
        cur.close()
        return dict(footer_content=footer_content)
    except Exception as e:
        # Jika ada error (misal DB belum siap), kirim None agar tidak crash
        return dict(footer_content=None)

# Decorator untuk Cek Login dan Admin
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'loggedin' not in session:
            flash('Silakan login terlebih dahulu.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if session.get('role') != 'admin':
            flash('Anda tidak memiliki izin untuk mengakses halaman ini.', 'danger')
            return redirect(url_for('home'))
        return f(*args, **kwargs)
    return decorated_function

# Bagian Login & Logout
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()
        if user and user['password'] == password: # Ingat untuk menggunakan hashing di produksi!
            session['loggedin'] = True
            session['id'] = user['id']
            session['username'] = user['username']
            session['role'] = user['role']
            flash('Login berhasil!', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Username atau password salah.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah berhasil logout.', 'success')
    return redirect(url_for('login'))

# Route Halaman Publik
@app.route('/')
def home():
    cur = mysql.connection.cursor()
    # Ambil 4 produk terbaru untuk ditampilkan di home
    cur.execute("SELECT * FROM product ORDER BY id DESC LIMIT 4")
    products = cur.fetchall()
    # Ambil konten dinamis untuk halaman utama
    cur.execute("SELECT page_value FROM content WHERE page_key = 'home_welcome'")
    home_content = cur.fetchone()
    cur.execute("SELECT page_value FROM content WHERE page_key = 'service_page'")
    service_content = cur.fetchone()
    cur.close()
    return render_template('home.html', produk=products, home_content=home_content, service_content=service_content)

@app.route('/product')
def product():
    cur = mysql.connection.cursor()
    query = "SELECT p.*, c.name_category FROM product p JOIN category c ON p.category = c.id_category"
    cur.execute(query)
    products = cur.fetchall()
    cur.close()
    return render_template('product.html', produk=products)

@app.route('/about')
def about():
    cur = mysql.connection.cursor()
    cur.execute("SELECT page_value FROM content WHERE page_key = 'about_page'")
    content = cur.fetchone()
    cur.close()
    return render_template('about.html', content=content)

@app.route('/service')
def service_page(): # Nama fungsi diubah agar tidak bentrok dengan 'service.html'
    cur = mysql.connection.cursor()
    cur.execute("SELECT page_value FROM content WHERE page_key = 'service_page'")
    content = cur.fetchone()
    cur.close()
    return render_template('service.html', content=content)

@app.route('/detail-produk/<int:id>')
def detail_produk(id):
    cur = mysql.connection.cursor()
    query_detail = """
        SELECT p.*, c.name_category 
        FROM product p 
        JOIN category c ON p.category = c.id_category 
        WHERE p.id = %s
    """
    cur.execute(query_detail, [id])
    product_detail = cur.fetchone()
    if not product_detail:
        cur.close()
        abort(404)
    query_others = "SELECT * FROM product WHERE id != %s ORDER BY RAND() LIMIT 4"
    cur.execute(query_others, [id])
    other_products = cur.fetchall()
    cur.close()
    return render_template('detail-product.html', detail=product_detail, produk=other_products)

@app.route('/search-product')
def search_product():
    keyword = request.args.get('keyword', '') 
    cur = mysql.connection.cursor()
    query = "SELECT * FROM product WHERE name_product LIKE %s"
    cur.execute(query, (f"%{keyword}%",))
    products = cur.fetchall()
    cur.close()
    return render_template('product.html', produk=products)

@app.template_filter('rupiah')
def format_rupiah(value):
    try:
        return f"{int(value):,}".replace(',', '.')
    except (ValueError, TypeError):
        return "0" 

# Route Admin Panel dan Manajemen
@app.route('/admin/dashboard')
@login_required
@admin_required
def admin_dashboard():
    cur = mysql.connection.cursor()
    
    # 1. Mengambil data statistik
    cur.execute("SELECT COUNT(*) as total FROM product")
    total_products = cur.fetchone()['total']
    
    cur.execute("SELECT COUNT(*) as total FROM category")
    total_categories = cur.fetchone()['total']
    
    cur.execute("SELECT COUNT(*) as total FROM users")
    total_users = cur.fetchone()['total']
    
    # 2. Mengambil 5 produk terbaru
    cur.execute("SELECT id, name_product FROM product ORDER BY id DESC LIMIT 5")
    recent_products = cur.fetchall()
    
    cur.close()
    
    # Membuat dictionary untuk dikirim ke template
    stats = {
        'total_products': total_products,
        'total_categories': total_categories,
        'total_users': total_users
    }
    
    return render_template('admin_dashboard.html', stats=stats, recent_products=recent_products)

# ... (sisa kode app.py biarkan saja)

# (Manajemen Produk: Tambah, Simpan, Edit, Update, Hapus)
@app.route('/add-product')
@login_required
@admin_required
def add_product():
    cur = mysql.connection.cursor()
    cur.execute('SELECT p.*, c.name_category FROM product p JOIN category c ON p.category = c.id_category ORDER BY p.id DESC')
    products = cur.fetchall()
    cur.execute('SELECT * FROM category')
    categories = cur.fetchall()
    cur.close()
    return render_template('add-product.html', produk=products, kategori=categories)

@app.route('/save-product', methods=['POST'])
@login_required
@admin_required
def save_product():
    name_product = request.form['name_product']
    image_URL = request.form['image_url']
    price = request.form['price']
    category = request.form['category']
    in_stok = request.form['in_stok']
    cur = mysql.connection.cursor()
    query = 'INSERT INTO product (name_product, image_url, price, category, in_stok) VALUES (%s, %s, %s, %s, %s)'
    cur.execute(query, (name_product, image_URL, price, category, in_stok))
    mysql.connection.commit()
    cur.close()
    flash('Produk berhasil ditambahkan', 'success')
    return redirect(url_for('add_product'))

@app.route('/edit-product/<int:id>')
@login_required
@admin_required
def edit_product(id):
    cur = mysql.connection.cursor()
    cur.execute('SELECT * FROM product WHERE id = %s', [id])
    product_data = cur.fetchone() 
    cur.execute('SELECT * FROM category')
    categories = cur.fetchall()
    cur.close()
    return render_template('edit-product.html', produk=product_data, kategori=categories)

@app.route('/update-product/<int:id>', methods=['POST'])
@login_required
@admin_required
def update_product(id):
    name_product = request.form['name_product']
    image_URL = request.form['image_url']
    price = request.form['price']
    category = request.form['category']
    in_stok = request.form['in_stok']
    cur = mysql.connection.cursor()
    query = 'UPDATE product SET name_product = %s, image_url = %s, price = %s, category = %s, in_stok = %s WHERE id = %s'
    cur.execute(query, (name_product, image_URL, price, category, in_stok, id))
    mysql.connection.commit()
    cur.close()
    flash('Produk berhasil diperbarui', 'success')
    return redirect(url_for('add_product'))

@app.route('/delete-product/<int:id>')
@login_required
@admin_required
def delete_product(id):
    cur = mysql.connection.cursor()
    query = 'DELETE FROM product WHERE id = %s'
    cur.execute(query, [id])
    mysql.connection.commit()
    cur.close()
    flash('Produk berhasil dihapus', 'danger')
    return redirect(url_for('add_product'))

# Manajemen Konten Dinamis
def content_manager(template_name, page_key, page_title):
    cur = mysql.connection.cursor()
    if request.method == 'POST':
        content_value = request.form['content']
        cur.execute("UPDATE content SET page_value = %s WHERE page_key = %s", (content_value, page_key))
        mysql.connection.commit()
        flash(f'Konten {page_title} berhasil diperbarui!', 'success')
    cur.execute("SELECT page_value FROM content WHERE page_key = %s", (page_key,))
    content = cur.fetchone()
    cur.close()
    return render_template(template_name, content=content, page_title=page_title)

@app.route('/admin/manage/home', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_home():
    return content_manager('manage_content.html', 'home_welcome', 'Halaman Utama')

@app.route('/admin/manage/about', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_about():
    return content_manager('manage_content.html', 'about_page', 'Halaman About')

@app.route('/admin/manage/layanan', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_layanan():
    return content_manager('manage_content.html', 'service_page', 'Halaman Layanan')

@app.route('/admin/manage/footer', methods=['GET', 'POST'])
@login_required
@admin_required
def manage_footer():
    return content_manager('manage_content.html', 'footer_content', 'Footer')

if __name__ == '__main__':
    app.run(debug=True) 