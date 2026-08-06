# Presentation Notes: SEC Open Data Portfolio Backtester

ไฟล์นี้ใช้เป็นโน้ตสำหรับ present งาน CQF Module 1-2 โดยอธิบายว่า project นี้ทำอะไร ใช้งานกับ objective แบบใด และระบบทำงานอย่างไรตั้งแต่รับ input จนออกผลลัพธ์

## 1. Project นี้คืออะไร

Project นี้คือเว็บแอปสำหรับทำ Portfolio Backtesting ด้วยข้อมูลกองทุนจาก SEC Open Data เท่านั้น จุดประสงค์คือให้ผู้ใช้ทั่วไปสามารถเลือกกองทุน ใส่น้ำหนักพอร์ต เลือกช่วงเวลา และเลือก objective การใช้งาน แล้วระบบจำลองผลตอบแทนย้อนหลัง ความเสี่ยง drawdown การเทียบ benchmark ผลของ cashflow และผลของ rebalancing ออกมาเป็น dashboard และ CQF report

แนวคิดหลักของระบบ:

- ใช้ข้อมูลจริงจาก SEC Open Data ไม่ใช้ข้อมูล mock ใน production result
- วิเคราะห์จาก NAV รายวันของกองทุน แล้ว resample เป็น month-end เพื่อคำนวณ return รายเดือน
- ให้ผู้ใช้เลือก objective ก่อน เพื่อ auto-fill parameter เริ่มต้น
- ผู้ใช้ยังแก้ parameter เองได้ทั้งหมดหลัง auto-fill
- ทุก run ถูกบันทึกเป็น `request.json`, `result.json`, และ export เป็น `cqf_report.md`
- ตัวเลขสำคัญสามารถ reproduce ได้จาก cached SEC NAV data ด้วย verifier script

## 2. ทำไมต้องมี Objective Preset

Portfolio backtesting มี input เยอะ เช่น สัดส่วนพอร์ต ช่วงเวลา เงินเริ่มต้น benchmark cashflow rebalancing cost slippage และ risk-free rate ถ้าให้ผู้ใช้เริ่มจากหน้าว่างทั้งหมดจะใช้งานยาก

ระบบนี้จึงให้ผู้ใช้เลือก objective ก่อน เช่น Past Performance หรือ Monthly DCA จากนั้นระบบ auto-fill ค่าเริ่มต้นที่เหมาะกับ use case นั้น แต่ยังเปิดให้แก้ต่อเองได้

หลักการนี้คล้ายเครื่องมือ portfolio backtester มืออาชีพที่มักมี input หลักเป็น allocation, date range, initial capital, benchmark, contribution/withdrawal, rebalancing และ cost assumptions เช่น Portfolio Visualizer, Testfol.io และเครื่องมือ backtesting อื่น ๆ

## 3. Use Case 1: Past Performance

### คำถามหลัก

ถ้าถือพอร์ตนี้ในอดีต ช่วงเวลาที่เลือก ผลลัพธ์จะเป็นอย่างไร

### เหมาะกับใคร

- นักลงทุนที่อยากรู้ว่าพอร์ตที่เลือกเคยโตหรือขาดทุนอย่างไร
- ผู้เรียนที่อยากอธิบาย performance และ risk ของ allocation หนึ่ง
- คนที่ต้องการเทียบพอร์ตกับ benchmark แบบง่ายที่สุด

### Parameter ที่ระบบ auto-fill

- Cashflow: ปิด
- Rebalancing: annual
- Transaction cost: 0 bps
- Slippage: 0 bps
- Annual drag: 0%

### Input ที่ต้องดูและตั้งค่า

Required:

- SEC funds and weights: เลือกกองทุนและกำหนดน้ำหนักรวม 100%
- Start date: วันเริ่ม backtest
- End date: วันสิ้นสุด backtest
- Initial capital: เงินเริ่มต้น
- Benchmark fund: กองทุนที่ใช้เทียบผลลัพธ์

Optional:

- Rebalancing mode
- Costs
- Risk-free rate

### Output ที่ต้องดูหลัก ๆ

- Ending Value: เงินปลายทางจากเงินตั้งต้น
- TWRR / TWRR CAGR: ผลตอบแทนของ strategy โดยไม่ให้ cashflow บิดผลลัพธ์
- Volatility: ความผันผวนรายปี
- Sharpe Ratio: ผลตอบแทนส่วนเกินต่อความเสี่ยง
- Max Drawdown: ช่วงขาดทุนหนักสุดจาก peak ถึง trough
- Benchmark Excess Return: พอร์ตชนะหรือแพ้ benchmark เท่าไร
- Equity Curve: เส้นมูลค่าพอร์ตตลอดเวลา
- Drawdown Curve: เห็นช่วง stress ของพอร์ต
- Annual/Monthly Returns: ดูว่าปีหรือเดือนไหนเป็นตัวขับผลลัพธ์

### วิธี present

Past Performance เป็น baseline use case ของระบบ ใช้ตอบคำถามว่า allocation ที่เลือกมี historical profile อย่างไร โดยไม่ใส่เงินเพิ่มและไม่ถอนเงิน จึงเหมาะสำหรับเริ่มอธิบาย performance measurement ก่อนจะไปกรณี cashflow หรือ rebalancing

## 4. Use Case 2: Monthly DCA

### คำถามหลัก

ถ้าลงทุนเพิ่มทุกเดือน พอร์ตจะเติบโตอย่างไร และเงินที่เติมเข้าไปส่งผลต่อผลลัพธ์มากแค่ไหน

### เหมาะกับใคร

- นักลงทุนรายเดือน
- คนเริ่มสะสมกองทุนระยะยาว
- คนที่อยากเปรียบเทียบผลตอบแทนของพอร์ตกับพฤติกรรมการเติมเงินจริง

### Parameter ที่ระบบ auto-fill

- Cashflow: enabled
- Cashflow type: contribution
- Amount: 500 ต่อเดือน
- Frequency: monthly
- Timing: end of period
- Rebalancing: annual

### Input ที่ต้องดูและตั้งค่า

Required:

- SEC funds and weights
- Monthly contribution amount
- Start date
- End date
- Initial capital

Optional:

- Benchmark fund
- Rebalancing mode
- Costs
- Risk-free rate

### Output ที่ต้องดูหลัก ๆ

- Total Contributed: เงินทั้งหมดที่ใส่เข้าไป รวม initial capital
- Ending Value: มูลค่าพอร์ตปลายทาง
- Net Profit: ending value ลบเงินที่ใส่จริง
- Cashflow Count: จำนวนงวดที่ลงทุนเพิ่ม
- TWRR CAGR: performance ของ strategy
- Equity Curve: มูลค่าพอร์ตที่รวมผลของเงินลงทุนรายเดือน
- Cashflows Tab: ตรวจว่าระบบใส่เงินถูกเดือน ถูกจำนวน
- Benchmark Risk: ดูว่าพอร์ตที่ DCA มี risk-adjusted profile เทียบ benchmark อย่างไร

### สิ่งที่ต้องระวังตอนอธิบาย

ใน DCA เงินปลายทางที่สูงขึ้นไม่ได้แปลว่า strategy เก่งขึ้นเสมอ เพราะอาจเกิดจากการเติมเงินเพิ่ม ดังนั้นต้องแยกดู `Total Contributed`, `Net Profit`, และ `TWRR` คู่กัน

### วิธี present

Monthly DCA ทำให้ backtest เข้าใกล้ชีวิตจริงมากขึ้น เพราะนักลงทุนส่วนใหญ่ไม่ได้ลงทุนก้อนเดียว แต่ทยอยลงทุนทุกเดือน การดู TWRR ช่วยแยก performance ของพอร์ตออกจากผลของจำนวนเงินที่ใส่เพิ่ม

## 5. Use Case 3: Monthly Withdrawal

### คำถามหลัก

ถ้าถอนเงินออกทุกเดือน พอร์ตจะอยู่รอดหรือหมดเงิน และช่วงตลาดแย่จะกระทบแค่ไหน

### เหมาะกับใคร

- คนวางแผนเกษียณ
- คนต้องการใช้พอร์ตสร้างกระแสเงินสด
- คนที่อยากทดสอบ withdrawal plan กับ historical drawdown

### Parameter ที่ระบบ auto-fill

- Initial capital: อย่างน้อย 100,000
- Cashflow: enabled
- Cashflow type: withdrawal
- Amount: 1,000 ต่อเดือน
- Frequency: monthly
- Timing: end of period
- Rebalancing: annual

### Input ที่ต้องดูและตั้งค่า

Required:

- SEC funds and weights
- Monthly withdrawal amount
- Start date
- End date
- Starting capital

Optional:

- Benchmark fund
- Rebalancing mode
- Costs
- Risk-free rate

### Output ที่ต้องดูหลัก ๆ

- Total Withdrawn: ถอนออกไปทั้งหมดเท่าไร
- Ending Value: เหลือเงินปลายทางเท่าไร
- Portfolio Survived/Depleted: พอร์ตยังเหลือหรือหมด
- Max Drawdown: ช่วงขาดทุนหนักสุด
- Drawdown Stress: ถ้าเจอ shock -10%, -20%, -35% จะเหลือเท่าไร
- Cashflows Tab: ตรวจจำนวนเงินถอนในแต่ละงวด
- Monthly Returns: ดูว่า sequence of returns ช่วงต้นกระทบพอร์ตแค่ไหน

### สิ่งที่ต้องระวังตอนอธิบาย

Withdrawal use case ไม่ได้ดูแค่ return เฉลี่ย แต่ต้องดู timing ของผลตอบแทนด้วย ถ้าช่วงต้นเจอ drawdown หนักพร้อมถอนเงินทุกเดือน พอร์ตอาจเสียหายมากกว่าการขาดทุนเฉลี่ยทั่วไป

### วิธี present

Monthly Withdrawal เป็น use case ด้าน decumulation ไม่ใช่ accumulation ระบบจึงเน้นความอยู่รอดของพอร์ต เงินที่ถอนออกไปแล้ว และ drawdown stress มากกว่าดูเฉพาะ CAGR

## 6. Use Case 4: Rebalancing Impact

### คำถามหลัก

การ rebalance กลับไปที่ target weight ช่วยหรือทำร้ายผลลัพธ์ หลังรวม turnover และ cost แล้วเป็นอย่างไร

### เหมาะกับใคร

- นักลงทุนที่มีหลายกองทุนในพอร์ต
- คนที่อยากรู้ว่าควร rebalance รายเดือน รายไตรมาส รายปี หรือไม่ rebalance
- ผู้เรียนที่ต้องการอธิบาย trade-off ระหว่าง risk control กับ transaction cost

### Parameter ที่ระบบ auto-fill

- Cashflow: ปิด
- Rebalancing: annual
- Transaction cost: 5 bps
- Slippage: 0 bps
- Annual drag: 0%

### Input ที่ต้องดูและตั้งค่า

Required:

- SEC funds and weights
- Start date
- End date
- Rebalancing mode

Optional:

- Benchmark fund
- Transaction cost
- Slippage
- Annual drag
- Risk-free rate

### Output ที่ต้องดูหลัก ๆ

- Rebalance Count: มีการ rebalance กี่ครั้ง
- Turnover: ต้องซื้อขายมากแค่ไหนเพื่อกลับไป target weight
- Total Costs: ค่า cost จาก transaction/slippage/drag
- Ending Value: ผลลัพธ์ปลายทางหลัง cost
- Max Drawdown: rebalance ลด drawdown หรือไม่
- Sharpe Ratio: risk-adjusted return ดีขึ้นหรือแย่ลง
- Rebalancing Tab: ดูวันที่ rebalance, turnover, cost
- Diversification Check: ดูว่าน้ำหนักพอร์ต drift หรือ concentration เสี่ยงเกินไปหรือไม่

### สิ่งที่ต้องระวังตอนอธิบาย

Rebalancing ไม่ได้แปลว่าผลตอบแทนต้องสูงขึ้นเสมอ เป้าหมายหลักคือควบคุมน้ำหนักพอร์ตและความเสี่ยง การ rebalance บ่อยเกินไปอาจเพิ่ม transaction cost และลด ending value ได้

### วิธี present

Rebalancing Impact ใช้แสดงแนวคิด portfolio management ที่ต้อง trade off ระหว่าง discipline, risk control, turnover และ cost ผลลัพธ์ที่ดีไม่ควรดูแค่ ending value แต่ควรดู drawdown, volatility, Sharpe, turnover และ total costs พร้อมกัน

## 7. Output ที่ต้องแสดงทุกครั้ง

ไม่ว่าจะเลือก objective ใด ระบบควรแสดง analysis core เหล่านี้เสมอ เพราะเป็นส่วนที่ช่วยให้ผลลัพธ์ fair, accurate และ complete

### Objective Summary

สรุปตามคำถามของ use case เช่น Past Performance จะเน้น CAGR/drawdown ส่วน DCA จะเน้นเงินลงทุนรวมและ net profit ส่วน Withdrawal จะเน้น survived/depleted และเงินที่ถอนออก

### Equity Curve

เส้นมูลค่าพอร์ตตลอดเวลา ใช้ดู growth path และช่วงที่พอร์ตเสียหาย ไม่ควรดูเฉพาะ ending value เพราะสองพอร์ตที่จบใกล้กันอาจมี journey ของความเสี่ยงต่างกันมาก

### Key Metrics

ค่าหลักที่ใช้สรุป performance และ risk:

- Ending Value
- TWRR
- TWRR CAGR
- Volatility
- Sharpe
- Max Drawdown
- Benchmark Excess Return
- Total Contributed
- Total Withdrawn
- Total Costs

### Benchmark Risk

ใช้ตอบว่าพอร์ตชนะ benchmark เพราะรับ risk มากขึ้นหรือเพราะสร้าง excess performance ได้จริง ค่าหลักคือ beta, alpha, tracking error, information ratio และ correlation

### Drawdown Stress

ใช้ตอบ downside risk แบบเข้าใจง่าย เช่น ถ้าพอร์ตโดน -10%, -20%, -35% หรือ repeat max drawdown จะเหลือเงินเท่าไร

### Diversification Check

ดูว่า allocation กระจุกเกินไปหรือไม่ และสินทรัพย์ในพอร์ตเคลื่อนไหวสัมพันธ์กันแค่ไหน เพื่อไม่ให้เข้าใจผิดว่าถือหลายกองทุนแล้ว diversified เสมอ

### Annual/Monthly Returns

ช่วยแยกว่าผลลัพธ์เกิดจากปีใดหรือเดือนใด เช่น บางพอร์ต CAGR ดูดีเพราะมีปีเดียวที่เด้งแรง หรือ drawdown หนักเกิดในช่วงสั้น ๆ

### Quality Issues

แสดงปัญหาข้อมูล เช่น NAV หาย ข้อมูลไม่พอ หรือวันที่สุดท้าย stale เพื่อให้ผู้ใช้ไม่ quote ผลลัพธ์โดยไม่รู้ข้อจำกัดของข้อมูล

### CQF Report

สรุป methodology, formula, assumptions, data source, limitations และ reproducibility เพื่อส่งงานวิชาได้ และเพื่อให้ตัวเลขทุกตัวตรวจสอบย้อนกลับได้

## 8. Input และ Parameter ของระบบ

### Required Input

| Input | ความหมาย | ใช้ทำอะไร |
| --- | --- | --- |
| Objective | เลือก use case | กำหนด auto-fill และ summary ที่เหมาะกับคำถาม |
| SEC funds | กองทุนที่เลือกจาก SEC `proj_id` | ใช้ดึง NAV และสร้างพอร์ต |
| Weights | น้ำหนักแต่ละกองทุน | ใช้คำนวณ portfolio return และ rebalance target |
| Start date | วันเริ่มต้น | กำหนดช่วง NAV ที่ใช้ |
| End date | วันสิ้นสุด | กำหนดช่วง NAV ที่ใช้ |
| Initial capital | เงินเริ่มต้น | ใช้สร้างมูลค่าพอร์ตเริ่มต้น |
| Benchmark fund | กองทุน benchmark | ใช้เทียบ benchmark risk และ excess return |

### Optional / Advanced Input

| Input | ความหมาย | ใช้ทำอะไร |
| --- | --- | --- |
| Cashflow enabled | เปิด/ปิดเงินเข้าออกประจำ | ใช้กับ DCA และ withdrawal |
| Cashflow type | contribution หรือ withdrawal | บอกว่าเป็นเงินเติมหรือเงินถอน |
| Cashflow amount | จำนวนเงินต่อรอบ | ใช้ปรับ portfolio value |
| Cashflow frequency | monthly/quarterly/annual | กำหนดรอบของ cashflow |
| Cashflow timing | beginning/end | กำหนดว่าใส่หรือถอนต้นงวด/ปลายงวด |
| Rebalancing mode | none/monthly/quarterly/annual | กำหนดว่าจะ reset weight บ่อยแค่ไหน |
| Transaction bps | transaction cost | หัก cost จาก turnover |
| Slippage bps | slippage assumption | หัก cost เพิ่มจากการซื้อขาย |
| Annual drag pct | expense/drag ต่อปี | หักต้นทุนต่อเนื่อง |
| Risk-free rate pct | อัตราปลอดความเสี่ยงต่อปี | ใช้คำนวณ Sharpe และ alpha |
| Price field | NAV per unit | production ใช้ SEC NAV เท่านั้น |

## 9. หลักการทำงาน End-to-End

### Step 1: เตรียมข้อมูล SEC

ระบบ download ข้อมูลจาก SEC Open Data API แล้วเก็บไว้ใน local cache

- Raw source: SEC Open Data / Fund Daily Info
- Normalized NAV: `data/sec/normalized/daily_nav.parquet`
- Manifest: `data/sec/normalized/sec_data_manifest.json`

ข้อมูลหลักที่ใช้คือ NAV per unit ของแต่ละกองทุน โดยอ้าง `proj_id` เป็น identifier

### Step 2: ผู้ใช้เลือก Objective

ผู้ใช้เลือกหนึ่งใน 4 objective:

- Past Performance
- Monthly DCA
- Monthly Withdrawal
- Rebalancing Impact

เมื่อเลือก objective ระบบ auto-fill parameter ที่เหมาะกับ use case นั้น เช่น Monthly DCA จะเปิด contribution รายเดือน ส่วน Monthly Withdrawal จะเปิด withdrawal รายเดือน

### Step 3: ผู้ใช้เลือกกองทุนและน้ำหนักพอร์ต

ผู้ใช้เลือก SEC funds และตั้ง weight ให้รวมเป็น 100% ถ้า weight ไม่รวม 100% backend schema จะ reject request เพราะพอร์ตต้องมี target allocation ที่ชัดเจน

### Step 4: ผู้ใช้ตั้งช่วงเวลา เงินตั้งต้น benchmark และ advanced assumptions

ระบบรับ:

- Date range
- Initial capital
- Benchmark fund
- Cashflow rule
- Rebalancing rule
- Cost assumptions
- Risk-free rate

### Step 5: Backend validate request

Backend ตรวจ:

- Data source ต้องเป็น `sec_open_data`
- มี asset อย่างน้อย 1 กองทุน
- น้ำหนักรวมต้องเท่ากับ 100%
- Start date ต้องก่อน End date
- Objective ต้อง match กับ cashflow rule เช่น Monthly DCA ต้องเป็น monthly contribution

### Step 6: Load และ align NAV data

Backend โหลด NAV ของ selected funds และ benchmark จาก cache จากนั้น align ข้อมูลให้มีช่วงเวลาตรงกัน

กระบวนการหลัก:

1. Filter เฉพาะ `proj_id` ที่เกี่ยวข้อง
2. Resample และ align cache ของกองทุนที่เลือกทั้งหมดเป็น month-end
3. ถ้า label ของ period สุดท้ายใน cache หลัง resample เกินวัน NAV ล่าสุด ให้ cap label นั้นเป็นวัน NAV ล่าสุด
4. Backend filter ตาม start/end date เพื่อตรวจ quality issues จาก aligned panel
5. Engine filter panel เดียวกันตามช่วงวันที่เพื่อคำนวณ และ reject calculation ถ้า selected asset ขาด NAV ใน period ใดหรือมี calendar month หายไประหว่างทาง เพื่อไม่ให้ cashflow schedule ถูกบีบเวลา
6. Requested end date ที่มาก่อน final incomplete period ของ cache จะไม่สร้างหรือ cap partial month-end period ของตัวเอง

### Step 7: Apply beginning-of-period cashflow (ถ้าเลือก `beginning`)

เมื่อ cashflow ถึงกำหนดและตั้ง timing เป็น `beginning` ระบบ apply cashflow ก่อนรับผลตอบแทนของ period นั้น:

```text
contribution: values_t,start = values_t,start + target_weights * contribution_amount
withdrawal: values_t,start = values_t,start - current_weights * applied_withdrawal
```

ถ้า requested withdrawal มากกว่า portfolio value ระบบ cap ที่มูลค่าพอร์ตที่มีอยู่จริง

### Step 8: Apply NAV return และ annual drag

คำนวณ return จาก NAV:

```text
r_t = NAV_t / NAV_{t-1} - 1
```

จากนั้น apply return ตาม holdings value หลัง beginning cashflow (ถ้ามี) แล้วหัก annual drag ของ period:

```text
values_t,market = values_t,start * (1 + asset_returns_t)
period_drag = annual_drag_pct / 100 / 12
values_t,drag = values_t,market * (1 - period_drag)
```

### Step 9: Apply end-of-period cashflow (ถ้าเลือก `end`)

เมื่อ cashflow ถึงกำหนดและตั้ง timing เป็น `end` ระบบ apply หลัง NAV return และ annual drag:

```text
contribution: values_t,end = values_t,drag + target_weights * contribution_amount
withdrawal: values_t,end = values_t,drag - current_weights * applied_withdrawal
```

ดังนั้น execution order ต่อ period คือ:

```text
beginning: cashflow -> NAV return -> annual drag -> rebalancing -> trading costs
end:       NAV return -> annual drag -> cashflow -> rebalancing -> trading costs
```

ระบบบันทึก `total_contributed`, `total_withdrawn`, และ `cashflow_count` โดย `total_contributed` รวม initial capital ตั้งแต่เริ่มต้น แล้วจึงบวก applied contribution ที่เป็นบวก

### Step 10: Rebalancing และ trading costs

Transaction cost และ slippage คิดจาก turnover:

```text
cost_rate = (transaction_bps + slippage_bps) / 10,000
trade_cost = turnover * cost_rate
```

หลัง cashflow timing branch ของ period เสร็จ ถ้าถึงรอบ rebalance ระบบคำนวณน้ำหนักปัจจุบัน แล้ว reset holdings กลับไปที่ target weights จากนั้นจึงหัก transaction cost และ slippage

ผลที่บันทึก:

- Rebalance date
- Turnover
- Cost
- Before weights/value
- After weights/value

### Step 11: Calculate metrics

Metric หลัก:

```text
TWRR = product(1 + r_t) - 1
R_ann = product(1 + r_t)^(12 / n) - 1
sigma_ann = std(r_t) * sqrt(12)
Sharpe = (R_ann - R_f) / sigma_ann
DD_t = V_t / running_peak_t - 1
MDD = min(DD_t)
beta = cov(R_p, R_b) / var(R_b)
alpha = R_p,ann - [R_f + beta * (R_b,ann - R_f)]
```

### Step 12: Return dashboard output

Backend ส่งผลลัพธ์กลับ frontend เป็น sections:

- Objective Summary
- Equity Curve
- Benchmark Curve
- Drawdown Curve
- Monthly Returns
- Annual Returns
- Benchmark Risk
- Diversification
- Cashflows
- Rebalances
- Quality Issues
- Formula References

### Step 13: Persist run

ทุก run ถูกเก็บไว้ที่:

```text
data/runs/<run_id>/request.json
data/runs/<run_id>/result.json
```

ถ้า export CQF report จะได้:

```text
data/runs/<run_id>/cqf_report.md
```

### Step 14: Reproducibility verification

ระบบมี script สำหรับตรวจซ้ำ:

```bash
python3 scripts/sec_verify_run_reproducibility.py <run_id>
```

Script นี้อ่าน `request.json`, โหลด SEC NAV cache ปัจจุบัน, rerun engine ปัจจุบัน และ compare selected summary metrics กับ `result.json` ถ้า diff อยู่ใน tolerance จะได้ `ok: true` การตรวจสอบนี้ไม่ได้ restore NAV cache snapshot, dependency version, engine version หรือ report output ณ เวลาที่ run เดิมถูกสร้าง

## 10. สิ่งที่ควรพูดตอน Present

### Opening

งานนี้ไม่ใช่ Monte Carlo Simulation และไม่ใช่ Portfolio Optimization แต่เป็น Historical Portfolio Backtesting จุดประสงค์คือใช้ข้อมูล NAV จริงจาก SEC Open Data เพื่อดูว่า portfolio ที่กำหนดไว้จะมีผลลัพธ์อย่างไรในอดีต ภายใต้สมมติฐานที่ผู้ใช้กำหนด

### Main Point 1: Objective-driven UI

แทนที่จะให้ผู้ใช้เริ่มจาก parameter จำนวนมาก ระบบให้เลือก objective ก่อน แล้ว auto-fill settings ให้เหมาะกับ use case เช่น DCA จะเปิด monthly contribution ส่วน Withdrawal จะเปิด monthly withdrawal จากนั้นผู้ใช้ยังแก้ค่าทุกอย่างได้เอง

### Main Point 2: SEC-only production data

Production result ใช้ SEC Open Data เท่านั้น ข้อมูลที่ใช้คือ NAV ของกองทุนรวม โดย cache ไว้ก่อนคำนวณเพื่อให้ result reproducible

### Main Point 3: Performance ต้องดูคู่กับ Risk

ไม่ควรดูแค่ ending value หรือ CAGR เพราะพอร์ตที่ผลตอบแทนดีอาจมี drawdown สูง volatility สูง หรือ beta สูง ระบบจึงแสดง equity curve, drawdown, volatility, Sharpe, benchmark risk และ stress test ทุกครั้ง

### Main Point 4: Cashflow ต้องแยกจาก Skill

ใน DCA หรือ Withdrawal เงินเข้าออกทำให้ ending value เปลี่ยนมาก ดังนั้นระบบแยก total contributed, total withdrawn, TWRR, net profit และ cashflow history เพื่อไม่ให้สับสนระหว่าง performance ของ strategy กับผลของการเติมหรือถอนเงิน

### Main Point 5: Reproducibility

ทุก run มี request/result artifact และ verifier script เพื่อตรวจซ้ำ selected summary metrics จาก cached SEC NAV data; script ไม่ได้คำนวณซ้ำ report output ทั้งหมด

## 11. Slide Outline แนะนำ

1. Problem: portfolio backtesting สำหรับผู้ใช้ทั่วไปมักตั้งค่ายาก และผลลัพธ์อาจตีความผิด
2. Scope: ทำเฉพาะ Historical Portfolio Backtesting ไม่ทำ Monte Carlo และไม่ทำ Optimization
3. Data: SEC Open Data NAV cache
4. User Flow: เลือก objective -> เลือก funds/weights -> ตั้ง assumptions -> run -> อ่าน output -> export report
5. Four Use Cases: Past Performance, Monthly DCA, Monthly Withdrawal, Rebalancing Impact
6. Methodology: NAV return, TWRR, CAGR, volatility, drawdown, beta/alpha
7. Output: Summary, Growth, Drawdown, Returns, Metrics, Cashflows, Rebalancing, Report
8. Quality and Limitations: data issues, historical-only, not investment advice
9. Reproducibility: request/result/report artifacts and verifier
10. Demo: เลือกหนึ่ง objective แล้ว run ให้เห็น result

## 12. References

- SEC Open Data Services: https://secopendata.sec.or.th/
- SEC API Developer Portal, Fund Daily Info: https://api-portal.sec.or.th/apis
- SEC API change log describing Fund Daily Info daily NAV fields: https://api-portal.sec.or.th/changes
- Portfolio Visualizer analysis reference: https://www.portfoliovisualizer.com/analysis
- CFA Institute, Portfolio Performance Evaluation: https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/portfolio-performance-evaluation
- CFA Institute, Standard III(D) Performance Presentation: https://www.cfainstitute.org/standards/professionals/code-ethics-standards/standards-of-practice-iii-d
- CFA Institute digest on TWR and MWRR interpretation: https://rpc.cfainstitute.org/research/cfa-digest/2017/04/using-brinson-attribution-to-explain-the-differences-between-time-weighted-twr-and-money-weigh
- Testfol.io portfolio backtester reference: https://testfol.io/

## 13. Local Project Files Used

- `docs/objective-workflows.md`
- `docs/methodology.md`
- `docs/formula-reference.md`
- `frontend/src/objectives/objectives.ts`
- `backend/app/domain/schemas.py`
- `backend/app/engine/backtest.py`
- `backend/app/api/backtests.py`
