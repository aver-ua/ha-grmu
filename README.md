# Інтеграція ГРМУ (Газмережі) для Home Assistant

Кастомний компонент для [Home Assistant](https://www.home-assistant.io/), який отримує дані про розподіл газу, баланс, показники лічильника та дворічну історію споживання з особистого кабінету [my.grmu.com.ua](https://my.grmu.com.ua).

## 🤖 Про проєкт та розробку

## 🤖 Розробка

Код цього компонента та конфігурації графіків були згенеровані у співпраці з **Google Gemini** в режимі інтерактивного програмування.

## 🌟 Основні можливості

* **Зручна авторизація:** Налаштування через графічний інтерфейс Home Assistant (Config Flow).
* **Повна робота з Inertia.js:** Автоматична обробка CSRF-токанів, сесійних кукі та версіонування Inertia.
* **8 основних сенсорів:**
  * **Баланс** (`UAH`)
  * **Споживання за місяць** (`m³`)
  * **Тариф** (`UAH/m³`)
  * **Плата за розподіл** (місячна, `UAH`)
  * **Замовлена потужність** (місячна та річна, `m³`)
  * **Замовлена потужність на наступний рік** (місячна та річна, `m³`)
  * **Останні показники лічильника** (`m³`)
* **Деталізовані атрибути:**
  * Номер особового рахунку, EIC-код, адреса об'єкта.
  * Серійний номер лічильника, дата останнього зняття показників та джерело (фотофіксація, особистий кабінет тощо).
* **Дворічна історія:** Автоматичний Partial Reload за поточний та попередній роки для побудови графіків споживання та динаміки показників.

---

## 🛠️ Встановлення

### 1. Копіювання модулів інтеграції

1. Створіть директорію `grmu` у папці `/config/custom_components/` вашого Home Assistant.
2. Скопіюйте у створену папку файли інтеграції:
   * `__init__.py`
   * `manifest.json`
   * `const.py`
   * `config_flow.py`
   * `coordinator.py`
   * `sensor.py`
3. Перезапустіть Home Assistant.

### 2. Налаштування інтеграції

1. У Home Assistant перейдіть до **Налаштування** → **Пристрої та сервіси**.
2. Натисніть **Додати інтеграцію** в правому нижньому кутку.
3. Знайдіть **ГРМУ (Газорозподільні мережі України)** у списку.
4. Введіть ваш Email та Пароль від особистого кабінету `my.grmu.com.ua`.

---

## 📊 Візуалізація на дашборді (ApexCharts Card)

Для побудови графіків з історії в атрибутах сенсорів можна використовувати кастомну картку **ApexCharts Card**.

### 1. Графік споживання газу та енергії (м³ та кВт·год)

> **Примітка:** У коді враховано захист від від'ємних коригувальних значень.

```yaml
type: custom:apexcharts-card
header:
  show: true
  show_states: true
  colorize_states: true
  title: Споживання газу (м³) та енергії (кВт·год)
graph_span: 2y
apex_config:
  xaxis:
    labels:
      format: MM.yyyy
  yaxis:
    - min: 0
      title:
        text: м³
      decimalsInFloat: 0
    - min: 0
      opposite: true
      title:
        text: кВт·год
      decimalsInFloat: 0
series:
  - entity: sensor.osobovii_rakhunok_0000000000_grmu_spozhivannia_za_misiats
    name: Спожито (м³)
    type: column
    color: '#ff9800'
    data_generator: |
      const months = {
        'Січень': '01', 'Лютий': '02', 'Березень': '03', 'Квітень': '04',
        'Травень': '05', 'Червень': '06', 'Липень': '07', 'Серпень': '08',
        'Вересень': '09', 'Жовтень': '10', 'Листопад': '11', 'Грудень': '12'
      };
      const history = entity.attributes.consumption_history;
      if (!history) return [];
      return history.map((item) => {
        const m = months[item.MONTHIC] || '01';
        const timestamp = new Date(`${item.YEARIC}-${m}-01T00:00:00`).getTime();
        const rawVal = parseFloat(String(item.CALC_V || 0).replace(',', '.'));
        return [timestamp, Math.max(0, rawVal)];
      }).sort((a, b) => a[0] - b[0]);

  - entity: sensor.osobovii_rakhunok_0000000000_grmu_spozhivannia_za_misiats
    name: Енергія (кВт·год)
    type: line
    stroke_width: 2
    color: '#2196f3'
    data_generator: |
      const months = {
        'Січень': '01', 'Лютий': '02', 'Березень': '03', 'Квітень': '04',
        'Травень': '05', 'Червень': '06', 'Липень': '07', 'Серпень': '08',
        'Вересень': '09', 'Жовтень': '10', 'Листопад': '11', 'Грудень': '12'
      };
      const history = entity.attributes.consumption_history;
      if (!history) return [];
      return history.map((item) => {
        const m = months[item.MONTHIC] || '01';
        const timestamp = new Date(`${item.YEARIC}-${m}-01T00:00:00`).getTime();
        const rawVal = parseFloat(String(item.ENERGYKVT || 0).replace(',', '.'));
        return [timestamp, Math.max(0, rawVal)];
      }).sort((a, b) => a[0] - b[0]);