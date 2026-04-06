import time
from flask import Blueprint, render_template
from ..models import db
from ..helpers import admin_required

bench_bp = Blueprint('bench', __name__)

QUERIES = [
    {
        "title":      "Marketplace — all available products",
        "endpoint":   "GET /marketplace",
        "frequency":  "Every page visit",
        "category":   "Products",
        "indexes":    ["ix_products_avail_cat (is_available, category)", "created_at index for ORDER BY"],
        "sql":        "SELECT product_id,title,price,category,created_at FROM Products WHERE is_available=1 ORDER BY created_at DESC LIMIT 50",
        "explain":    "EXPLAIN SELECT product_id,title,price,category,created_at FROM Products WHERE is_available=1 ORDER BY created_at DESC LIMIT 50",
    },
    {
        "title":      "Marketplace — filtered by category",
        "endpoint":   "GET /marketplace?category=Books",
        "frequency":  "High",
        "category":   "Products",
        "indexes":    ["ix_products_avail_cat (is_available, category) — covers both WHERE conditions"],
        "sql":        "SELECT product_id,title,price,created_at FROM Products WHERE is_available=1 AND category='Books' ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT product_id,title,price,created_at FROM Products WHERE is_available=1 AND category='Books' ORDER BY created_at DESC",
    },
    {
        "title":      "My Listings page",
        "endpoint":   "GET /my-listings",
        "frequency":  "High",
        "category":   "Products",
        "indexes":    ["ix_products_seller_avail (seller_id, is_available) — composite"],
        "sql":        "SELECT product_id,title,price,is_available FROM Products WHERE seller_id=1 ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT product_id,title,price,is_available FROM Products WHERE seller_id=1 ORDER BY created_at DESC",
    },
    {
        "title":      "Chat conversation",
        "endpoint":   "GET /chat/<id> (polled every 5s)",
        "frequency":  "Extremely high",
        "category":   "Chat",
        "indexes":    ["ix_chat_sender_receiver (sender_id, receiver_id) — composite covers OR condition"],
        "sql":        "SELECT chat_id,sender_id,message,created_at FROM Chat WHERE (sender_id=1 AND receiver_id=2) OR (sender_id=2 AND receiver_id=1) ORDER BY created_at ASC",
        "explain":    "EXPLAIN SELECT chat_id,sender_id,message,created_at FROM Chat WHERE (sender_id=1 AND receiver_id=2) OR (sender_id=2 AND receiver_id=1) ORDER BY created_at ASC",
    },
    {
        "title":      "Unread messages count (navbar badge)",
        "endpoint":   "Every page — context processor",
        "frequency":  "Every single page load",
        "category":   "Chat",
        "indexes":    ["ix_chat_receiver_read (receiver_id, is_read) — composite, no table scan"],
        "sql":        "SELECT COUNT(*) FROM Chat WHERE receiver_id=1 AND is_read=0",
        "explain":    "EXPLAIN SELECT COUNT(*) FROM Chat WHERE receiver_id=1 AND is_read=0",
    },
    {
        "title":      "Unread notifications count (navbar bell)",
        "endpoint":   "Every page — context processor",
        "frequency":  "Every single page load",
        "category":   "Notifications",
        "indexes":    ["ix_notifs_member_read (member_id, is_read) — composite"],
        "sql":        "SELECT COUNT(*) FROM Notifications WHERE member_id=1 AND is_read=0",
        "explain":    "EXPLAIN SELECT COUNT(*) FROM Notifications WHERE member_id=1 AND is_read=0",
    },
    {
        "title":      "Member portfolio — products",
        "endpoint":   "GET /profile/<id>",
        "frequency":  "Medium",
        "category":   "Products",
        "indexes":    ["ix_products_seller_avail (seller_id, is_available)"],
        "sql":        "SELECT product_id,title,price FROM Products WHERE seller_id=1 AND is_available=1 ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT product_id,title,price FROM Products WHERE seller_id=1 AND is_available=1 ORDER BY created_at DESC",
    },
    {
        "title":      "Admin logs",
        "endpoint":   "GET /admin/logs",
        "frequency":  "Low (admin only)",
        "category":   "Logs",
        "indexes":    ["ix_logs_member_action (member_id, action_type)", "timestamp index for ORDER BY"],
        "sql":        "SELECT log_id,member_id,action_type,description,timestamp FROM Logs ORDER BY timestamp DESC LIMIT 30",
        "explain":    "EXPLAIN SELECT log_id,member_id,action_type,description,timestamp FROM Logs ORDER BY timestamp DESC LIMIT 30",
    },
    {
        "title":      "Product search by title",
        "endpoint":   "GET /marketplace?search=laptop",
        "frequency":  "Medium",
        "category":   "Products",
        "indexes":    ["No index on title — full scan"],
        "sql":        "SELECT product_id,title,price FROM Products WHERE is_available=1 AND title LIKE '%laptop%' ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT product_id,title,price FROM Products WHERE is_available=1 AND title LIKE '%laptop%' ORDER BY created_at DESC",
    },
    {
        "title":      "Price range filter",
        "endpoint":   "GET /marketplace?min_price=100&max_price=500",
        "frequency":  "Medium",
        "category":   "Products",
        "indexes":    ["ix_products_avail_price (is_available, price)"],
        "sql":        "SELECT product_id,title,price FROM Products WHERE is_available=1 AND price BETWEEN 100 AND 500 ORDER BY price ASC",
        "explain":    "EXPLAIN SELECT product_id,title,price FROM Products WHERE is_available=1 AND price BETWEEN 100 AND 500 ORDER BY price ASC",
    },
    {
        "title":      "Transaction history — buyer",
        "endpoint":   "GET /transactions",
        "frequency":  "Medium",
        "category":   "Transactions",
        "indexes":    ["ix_txn_buyer_status (buyer_id, status)"],
        "sql":        "SELECT txn_id,product_id,amount,status,created_at FROM TransactionHistory WHERE buyer_id=1 ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT txn_id,product_id,amount,status,created_at FROM TransactionHistory WHERE buyer_id=1 ORDER BY created_at DESC",
    },
    {
        "title":      "Transaction history — seller",
        "endpoint":   "GET /transactions",
        "frequency":  "Medium",
        "category":   "Transactions",
        "indexes":    ["ix_txn_seller_status (seller_id, status)"],
        "sql":        "SELECT txn_id,product_id,amount,status,created_at FROM TransactionHistory WHERE seller_id=1 ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT txn_id,product_id,amount,status,created_at FROM TransactionHistory WHERE seller_id=1 ORDER BY created_at DESC",
    },
    {
        "title":      "Product reviews",
        "endpoint":   "GET /product/<id>",
        "frequency":  "Medium",
        "category":   "Reviews",
        "indexes":    ["product_id index"],
        "sql":        "SELECT review_id,rating,comment,created_at FROM Reviews WHERE product_id=1 ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT review_id,rating,comment,created_at FROM Reviews WHERE product_id=1 ORDER BY created_at DESC",
    },
    {
        "title":      "User reviews given",
        "endpoint":   "GET /profile/<id>",
        "frequency":  "Low",
        "category":   "Reviews",
        "indexes":    ["reviewer_id index"],
        "sql":        "SELECT review_id,product_id,rating,comment FROM Reviews WHERE reviewer_id=1 ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT review_id,product_id,rating,comment FROM Reviews WHERE reviewer_id=1 ORDER BY created_at DESC",
    },
    {
        "title":      "Bargaining proposals on product",
        "endpoint":   "GET /product/<id>",
        "frequency":  "Medium",
        "category":   "Bargaining",
        "indexes":    ["ix_proposals_product_buyer (product_id, buyer_id)"],
        "sql":        "SELECT proposal_id,buyer_id,proposed_price,message FROM Bargaining_Proposals WHERE product_id=1 ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT proposal_id,buyer_id,proposed_price,message FROM Bargaining_Proposals WHERE product_id=1 ORDER BY created_at DESC",
    },
    {
        "title":      "User's bargaining proposals",
        "endpoint":   "GET /profile/<id>",
        "frequency":  "Low",
        "category":   "Bargaining",
        "indexes":    ["buyer_id index"],
        "sql":        "SELECT proposal_id,product_id,proposed_price,status FROM Bargaining_Proposals WHERE buyer_id=1 ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT proposal_id,product_id,proposed_price,status FROM Bargaining_Proposals WHERE buyer_id=1 ORDER BY created_at DESC",
    },
    {
        "title":      "Open demands",
        "endpoint":   "GET /demands",
        "frequency":  "Medium",
        "category":   "Demands",
        "indexes":    ["ix_demands_status_cat (status, category)"],
        "sql":        "SELECT demand_id,title,category,budget FROM Demands WHERE status='open' ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT demand_id,title,category,budget FROM Demands WHERE status='open' ORDER BY created_at DESC",
    },
    {
        "title":      "Demands by category",
        "endpoint":   "GET /demands?category=Electronics",
        "frequency":  "Medium",
        "category":   "Demands",
        "indexes":    ["ix_demands_status_cat (status, category)"],
        "sql":        "SELECT demand_id,title,budget FROM Demands WHERE status='open' AND category='Electronics' ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT demand_id,title,budget FROM Demands WHERE status='open' AND category='Electronics' ORDER BY created_at DESC",
    },
    {
        "title":      "User's demands",
        "endpoint":   "GET /profile/<id>",
        "frequency":  "Low",
        "category":   "Demands",
        "indexes":    ["member_id index"],
        "sql":        "SELECT demand_id,title,status FROM Demands WHERE member_id=1 ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT demand_id,title,status FROM Demands WHERE member_id=1 ORDER BY created_at DESC",
    },
    {
        "title":      "Purchase requests on product",
        "endpoint":   "GET /product/<id>",
        "frequency":  "Medium",
        "category":   "PurchaseRequests",
        "indexes":    ["product_id index"],
        "sql":        "SELECT request_id,buyer_id,message FROM PurchaseRequests WHERE product_id=1 ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT request_id,buyer_id,message FROM PurchaseRequests WHERE product_id=1 ORDER BY created_at DESC",
    },
    {
        "title":      "User's purchase requests",
        "endpoint":   "GET /profile/<id>",
        "frequency":  "Low",
        "category":   "PurchaseRequests",
        "indexes":    ["buyer_id index"],
        "sql":        "SELECT request_id,product_id,status FROM PurchaseRequests WHERE buyer_id=1 ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT request_id,product_id,status FROM PurchaseRequests WHERE buyer_id=1 ORDER BY created_at DESC",
    },
    {
        "title":      "Member directory",
        "endpoint":   "GET /members",
        "frequency":  "Low",
        "category":   "Members",
        "indexes":    ["No specific index — full scan"],
        "sql":        "SELECT member_id,name,email FROM Members ORDER BY name ASC",
        "explain":    "EXPLAIN SELECT member_id,name,email FROM Members ORDER BY name ASC",
    },
    {
        "title":      "Admin members list",
        "endpoint":   "GET /admin/members",
        "frequency":  "Low (admin)",
        "category":   "Members",
        "indexes":    ["role index"],
        "sql":        "SELECT member_id,name,email,role FROM Members ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT member_id,name,email,role FROM Members ORDER BY created_at DESC",
    },
    {
        "title":      "Student details",
        "endpoint":   "GET /profile/<id>",
        "frequency":  "Low",
        "category":   "Students",
        "indexes":    ["member_id index"],
        "sql":        "SELECT college_name,department,year FROM Students WHERE member_id=1",
        "explain":    "EXPLAIN SELECT college_name,department,year FROM Students WHERE member_id=1",
    },
    {
        "title":      "Feedback list",
        "endpoint":   "GET /admin/feedbacks",
        "frequency":  "Low (admin)",
        "category":   "Feedbacks",
        "indexes":    ["member_id index"],
        "sql":        "SELECT feedback_id,subject,message FROM Feedbacks ORDER BY created_at DESC LIMIT 20",
        "explain":    "EXPLAIN SELECT feedback_id,subject,message FROM Feedbacks ORDER BY created_at DESC LIMIT 20",
    },
    {
        "title":      "User feedback",
        "endpoint":   "GET /feedback",
        "frequency":  "Low",
        "category":   "Feedbacks",
        "indexes":    ["member_id index"],
        "sql":        "SELECT feedback_id,subject,message FROM Feedbacks WHERE member_id=1 ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT feedback_id,subject,message FROM Feedbacks WHERE member_id=1 ORDER BY created_at DESC",
    },
    {
        "title":      "Recent logs",
        "endpoint":   "GET /admin/logs",
        "frequency":  "Low (admin)",
        "indexes":    ["timestamp index"],
        "category":   "Logs",
        "sql":        "SELECT log_id,action_type,description FROM Logs WHERE timestamp > DATE_SUB(NOW(), INTERVAL 1 DAY) ORDER BY timestamp DESC",
        "explain":    "EXPLAIN SELECT log_id,action_type,description FROM Logs WHERE timestamp > DATE_SUB(NOW(), INTERVAL 1 DAY) ORDER BY timestamp DESC",
    },
    {
        "title":      "User logs",
        "endpoint":   "GET /admin/user/<id>",
        "frequency":  "Low (admin)",
        "category":   "Logs",
        "indexes":    ["ix_logs_member_action (member_id, action_type)"],
        "sql":        "SELECT log_id,action_type,description FROM Logs WHERE member_id=1 ORDER BY timestamp DESC LIMIT 10",
        "explain":    "EXPLAIN SELECT log_id,action_type,description FROM Logs WHERE member_id=1 ORDER BY timestamp DESC LIMIT 10",
    },
    {
        "title":      "Pending transactions",
        "endpoint":   "GET /admin/transactions",
        "frequency":  "Low (admin)",
        "category":   "Transactions",
        "indexes":    ["status index"],
        "sql":        "SELECT txn_id,buyer_id,seller_id,amount FROM TransactionHistory WHERE status='pending' ORDER BY created_at DESC",
        "explain":    "EXPLAIN SELECT txn_id,buyer_id,seller_id,amount FROM TransactionHistory WHERE status='pending' ORDER BY created_at DESC",
    },
    {
        "title":      "Completed transactions count",
        "endpoint":   "Dashboard stats",
        "frequency":  "Medium",
        "category":   "Transactions",
        "indexes":    ["status index"],
        "sql":        "SELECT COUNT(*) FROM TransactionHistory WHERE status='completed'",
        "explain":    "EXPLAIN SELECT COUNT(*) FROM TransactionHistory WHERE status='completed'",
    },
    {
        "title":      "Average product price by category",
        "endpoint":   "Analytics",
        "frequency":  "Low",
        "category":   "Products",
        "indexes":    ["category index"],
        "sql":        "SELECT category, AVG(price) as avg_price FROM Products WHERE is_available=1 GROUP BY category",
        "explain":    "EXPLAIN SELECT category, AVG(price) as avg_price FROM Products WHERE is_available=1 GROUP BY category",
    },
    {
        "title":      "Top selling categories",
        "endpoint":   "Analytics",
        "frequency":  "Low",
        "category":   "Products",
        "indexes":    ["No index on joins — complex query"],
        "sql":        "SELECT p.category, COUNT(t.txn_id) as sales FROM Products p JOIN TransactionHistory t ON p.product_id = t.product_id WHERE t.status='completed' GROUP BY p.category ORDER BY sales DESC",
        "explain":    "EXPLAIN SELECT p.category, COUNT(t.txn_id) as sales FROM Products p JOIN TransactionHistory t ON p.product_id = t.product_id WHERE t.status='completed' GROUP BY p.category ORDER BY sales DESC",
    },
]


def run_explain(sql):
    try:
        result = db.session.execute(db.text(sql.strip()))
        cols   = list(result.keys())
        rows   = [dict(zip(cols, row)) for row in result.fetchall()]
        return rows, None
    except Exception as e:
        return [], str(e)


def time_query(sql, runs=5):
    clean = sql.strip()
    if clean.upper().startswith('EXPLAIN '):
        clean = clean[8:].strip()
    times = []
    for _ in range(runs):
        t0 = time.perf_counter()
        try:
            db.session.execute(db.text(clean))
            db.session.rollback()
        except Exception:
            db.session.rollback()
        times.append((time.perf_counter() - t0) * 1000)
    return {
        'min_ms': round(min(times), 3),
        'avg_ms': round(sum(times) / len(times), 3),
        'max_ms': round(max(times), 3),
        'runs':   runs,
    }


def get_all_indexes():
    try:
        rows = db.session.execute(db.text("""
            SELECT TABLE_NAME, INDEX_NAME,
                   GROUP_CONCAT(COLUMN_NAME ORDER BY SEQ_IN_INDEX SEPARATOR ', ') AS columns,
                   NON_UNIQUE, INDEX_TYPE
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = DATABASE() AND INDEX_NAME != 'PRIMARY'
            GROUP BY TABLE_NAME, INDEX_NAME, NON_UNIQUE, INDEX_TYPE
            ORDER BY TABLE_NAME, INDEX_NAME
        """))
        cols = list(rows.keys())
        return [dict(zip(cols, r)) for r in rows.fetchall()]
    except Exception:
        return []


@bench_bp.route('/admin/benchmark')
@admin_required
def benchmark_dashboard():
    results = []
    for q in QUERIES:
        explain_rows, err = run_explain(q['explain'])
        timing = time_query(q['explain'])

        row = explain_rows[0] if explain_rows else {}
        access_type   = str(row.get('type',          row.get('access_type', 'N/A')))
        possible_keys = str(row.get('possible_keys', 'N/A'))
        key_used      = str(row.get('key',           'N/A'))
        rows_examined = str(row.get('rows',          row.get('rows_examined', 'N/A')))
        extra_info    = str(row.get('Extra',         row.get('extra', 'N/A')))
        is_optimized  = access_type not in ('ALL', 'N/A', 'None')

        results.append({**q,
                        'explain_rows':  explain_rows,
                        'explain_err':   err,
                        'timing':        timing,
                        'access_type':   access_type,
                        'possible_keys': possible_keys,
                        'key_used':      key_used,
                        'rows_examined': rows_examined,
                        'extra_info':    extra_info,
                        'is_optimized':  is_optimized})

    all_indexes     = get_all_indexes()
    optimized_count = sum(1 for r in results if r['is_optimized'])
    avg_ms          = round(sum(r['timing']['avg_ms'] for r in results) / len(results), 3)

    # Category-wise analytics
    categories = {}
    for r in results:
        cat = r.get('category', 'Other')
        if cat not in categories:
            categories[cat] = {'queries': [], 'avg_ms': 0, 'optimized': 0, 'total': 0}
        categories[cat]['queries'].append(r)
        categories[cat]['total'] += 1
        categories[cat]['optimized'] += 1 if r['is_optimized'] else 0
        categories[cat]['avg_ms'] += r['timing']['avg_ms']

    for cat in categories:
        categories[cat]['avg_ms'] = round(categories[cat]['avg_ms'] / categories[cat]['total'], 3)

    # Data for charts
    chart_data = {
        'categories': list(categories.keys()),
        'avg_times': [categories[cat]['avg_ms'] for cat in categories],
        'optimized_counts': [categories[cat]['optimized'] for cat in categories],
        'total_counts': [categories[cat]['total'] for cat in categories],
        'optimized_vs_scans': {
            'optimized': optimized_count,
            'scans': len(results) - optimized_count
        },
        'frequency_distribution': {}
    }

    # Frequency distribution
    freq_map = {}
    for r in results:
        freq = r['frequency'].split(' ')[0]  # Take first word
        freq_map[freq] = freq_map.get(freq, 0) + 1
    chart_data['frequency_distribution'] = freq_map

    return render_template('benchmark.html',
                           results=results, all_indexes=all_indexes,
                           total_queries=len(results),
                           optimized_count=optimized_count,
                           avg_query_ms=avg_ms,
                           categories=categories,
                           chart_data=chart_data)
