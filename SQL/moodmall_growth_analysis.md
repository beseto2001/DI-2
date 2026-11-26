# 성장 추이 분석: 모두몰

## Q1. 월별 매출의 누적 합계와 전월 대비 증감률은?

```sql
WITH monthly_sales AS (
  SELECT
    DATE_TRUNC(order_date, MONTH) AS sales_month,
    SUM(amount)                   AS revenue
  FROM project_name.dataset_name.orders
  WHERE status IN ('Paid', 'Shipped')
  GROUP BY sales_month
)
SELECT
  sales_month,
  revenue,
  SUM(revenue) OVER (ORDER BY sales_month)  AS cumulative_revenue,
  LAG(revenue) OVER (ORDER BY sales_month)  AS prev_month_revenue,
  ROUND(
    100.0 * (revenue - LAG(revenue) OVER (ORDER BY sales_month))
          / NULLIF(LAG(revenue) OVER (ORDER BY sales_month), 0)
  , 1)                                      AS mom_growth_pct
FROM monthly_sales
ORDER BY sales_month;
```

인사이트: 12월에 전월 대비 -32.7%로 떨어졌다가 1월에 +74.2%(850,000)로 회복했고, 2월은 2/11까지만 데이터가 있어 -78.0%는 불완전 기간으로 봐야 합니다.

---

## Q2. 카테고리별 베스트셀러 순위는? (동점 처리 포함)

```sql
WITH category_sales AS (
  SELECT
    p.category,
    p.product_name,
    SUM(oi.quantity)                 AS units_sold,
    SUM(oi.quantity * oi.unit_price) AS revenue
  FROM project_name.dataset_name.order_items oi
  JOIN project_name.dataset_name.orders o
    ON oi.order_id = o.order_id
  JOIN project_name.dataset_name.products p
    ON oi.product_id = p.product_id
  WHERE o.status IN ('Paid', 'Shipped')
  GROUP BY p.category, p.product_name
)
SELECT
  category,
  product_name,
  units_sold,
  revenue,
  RANK() OVER (PARTITION BY category ORDER BY revenue DESC) AS category_rank
FROM category_sales
ORDER BY category, category_rank;
```

인사이트: Boots 안에서 워커 부츠(378,000)가 첼시 부츠(180,000)의 약 2.1배 매출을 내고 있어, 카테고리 성과가 1위 상품 한두 개에 쏠려 있습니다.

---

## Q3. 고객별 재구매 간격은 얼마나 되며, 간격이 점점 짧아지고 있나?

```sql
WITH completed_orders AS (
  SELECT
    customer_id,
    order_id,
    order_date
  FROM project_name.dataset_name.orders
  WHERE status IN ('Paid', 'Shipped')
),
with_gaps AS (
  SELECT
    customer_id,
    order_date,
    LAG(order_date)  OVER (PARTITION BY customer_id ORDER BY order_date) AS prev_order_date,
    LEAD(order_date) OVER (PARTITION BY customer_id ORDER BY order_date) AS next_order_date
  FROM completed_orders
)
SELECT
  customer_id,
  order_date,
  DATE_DIFF(order_date, prev_order_date, DAY) AS days_since_last_order,
  DATE_DIFF(next_order_date, order_date, DAY) AS days_until_next_order
FROM with_gaps
WHERE prev_order_date IS NOT NULL
ORDER BY customer_id, order_date;
```

인사이트: 재구매가 일어난 8명의 재구매 간격 중앙값은 58일이고, 3회 구매한 C001은 간격이 51일에서 58일로 늘어 간격이 짧아지는 추세는 보이지 않습니다.

---

## Q4. 카테고리별 누적 매출 점유율은 월마다 어떻게 바뀌었나?

```sql
WITH monthly_category AS (
  SELECT
    DATE_TRUNC(o.order_date, MONTH) AS sales_month,
    p.category,
    SUM(oi.quantity * oi.unit_price) AS revenue
  FROM project_name.dataset_name.orders o
  JOIN project_name.dataset_name.order_items oi
    ON o.order_id = oi.order_id
  JOIN project_name.dataset_name.products p
    ON oi.product_id = p.product_id
  WHERE o.status IN ('Paid', 'Shipped')
  GROUP BY sales_month, p.category
),
with_totals AS (
  SELECT
    sales_month,
    category,
    revenue,
    SUM(revenue) OVER (PARTITION BY category ORDER BY sales_month) AS category_cumulative,
    ROUND(
      100.0 * revenue / NULLIF(SUM(revenue) OVER (PARTITION BY sales_month), 0)
    , 1)                                                          AS monthly_share_pct
  FROM monthly_category
)
SELECT
  sales_month,
  category,
  revenue,
  category_cumulative,
  monthly_share_pct,
  DENSE_RANK() OVER (PARTITION BY sales_month ORDER BY revenue DESC) AS revenue_rank_in_month
FROM with_totals
ORDER BY sales_month, revenue_rank_in_month;
```

인사이트: Sandals는 누적 매출이 9월부터 1월까지 매달 1위를 유지하며 1월 기준 955,000에 이르는 반면, 월별 1위는 샌들(9~10월), 부츠(11월), 스니커즈(1월)로 계속 바뀌었습니다.

---

## Q5. 매달 매출 상위 3개 상품은 무엇이며, 그 상품이 계속 상위권에 머물렀나?

```sql
WITH monthly_product AS (
  SELECT
    DATE_TRUNC(o.order_date, MONTH) AS sales_month,
    p.product_name,
    SUM(oi.quantity * oi.unit_price) AS revenue
  FROM project_name.dataset_name.orders o
  JOIN project_name.dataset_name.order_items oi
    ON o.order_id = oi.order_id
  JOIN project_name.dataset_name.products p
    ON oi.product_id = p.product_id
  WHERE o.status IN ('Paid', 'Shipped')
  GROUP BY sales_month, p.product_name
),
ranked AS (
  SELECT
    sales_month,
    product_name,
    revenue,
    ROW_NUMBER() OVER (
      PARTITION BY sales_month
      ORDER BY revenue DESC, product_name
    ) AS rn
  FROM monthly_product
)
SELECT
  sales_month,
  rn AS monthly_rank,
  product_name,
  revenue
FROM ranked
WHERE rn <= 3
ORDER BY sales_month, rn;
```

인사이트: 월별 1위 상품이 매달 여름 샌들, 슬리퍼 샌들, 워커 부츠, 양말 세트, 캔버스 스니커즈로 모두 달랐고, 상위 3위에 3번 든 클래식 스니커즈가 가장 꾸준했습니다.
