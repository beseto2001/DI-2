# 모두몰 요약 리포트

## Q1. 우리 고객은 어떤 연령대·성별로 구성되어 있나?

```sql
SELECT CASE
         WHEN age < 20 THEN '1) 10대 이하'
         WHEN age < 30 THEN '2) 20대'
         WHEN age < 40 THEN '3) 30대'
         WHEN age < 50 THEN '4) 40대'
         ELSE               '5) 50대 이상'
       END        AS 연령대,
       gender     AS 성별,
       COUNT(*)   AS 고객수
FROM customers
GROUP BY 연령대, gender
ORDER BY 연령대, 성별;                      -- 라벨 앞 번호로 연령 순서 유지
```

## Q2. 지역별 고객 수와 VIP 비율은?

```sql
SELECT region                                                    AS 지역,
       COUNT(*)                                                  AS 고객수,
       SUM(CASE WHEN grade = 'VIP' THEN 1 ELSE 0 END)            AS VIP수,
       ROUND(SUM(CASE WHEN grade = 'VIP' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 1) AS VIP비율_퍼센트
FROM customers
GROUP BY region
HAVING COUNT(*) >= 10                       -- HAVING: 고객이 너무 적은 지역(그룹) 제외
ORDER BY VIP비율_퍼센트 DESC;               -- VIP 비율 높은 지역부터
```

## Q3. 월별로 실제 구매한 고객은 몇 명이고, 1인당 얼마 썼나?

```sql
SELECT SUBSTR(order_date, 1, 7)                                     AS 주문월,
       COUNT(DISTINCT customer_id)                                  AS 구매고객수,
       COUNT(*)                                                     AS 주문수,
       SUM(total_amount)                                            AS 총매출,
       ROUND(SUM(total_amount) * 1.0 / COUNT(DISTINCT customer_id)) AS 고객당매출
FROM orders
WHERE status <> '취소'                     -- WHERE: 그룹 만들기 전에 취소 주문 행 제거
GROUP BY SUBSTR(order_date, 1, 7)
ORDER BY 주문월;                            -- 시간 순 → 추이
```

## Q4. 전체 주문은 상태별로 어떻게 나뉘나?

```sql
SELECT status                                                     AS 주문상태,
       COUNT(*)                                                   AS 주문수,
       SUM(total_amount)                                          AS 금액합계,
       ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM orders), 1) AS 비중_퍼센트
FROM orders
GROUP BY status
ORDER BY 주문수 DESC;
```

## Q5. 월별 취소·반품률은 어떻게 변하나?

```sql
SELECT SUBSTR(order_date, 1, 7)                                          AS 주문월,
       COUNT(*)                                                          AS 전체주문수,
       SUM(CASE WHEN status IN ('취소', '반품') THEN 1 ELSE 0 END)       AS 취소반품수,
       ROUND(SUM(CASE WHEN status IN ('취소', '반품') THEN 1 ELSE 0 END) * 100.0
             / COUNT(*), 1)                                              AS 취소반품률_퍼센트
FROM orders
GROUP BY SUBSTR(order_date, 1, 7)
ORDER BY 주문월;
```
