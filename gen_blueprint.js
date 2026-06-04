const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType, LevelFormat, PageBreak, Header, Footer, PageNumber } = require('docx');
const fs = require('fs');

const border = { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' };
const borders = { top: border, bottom: border, left: border, right: border };
const hBorder = { style: BorderStyle.SINGLE, size: 1, color: '2E75B6' };
const hBorders = { top: hBorder, bottom: hBorder, left: hBorder, right: hBorder };

function h(level, text) {
  const lvl = [HeadingLevel.HEADING_1, HeadingLevel.HEADING_2, HeadingLevel.HEADING_3][level - 1];
  return new Paragraph({ heading: lvl, children: [new TextRun(text)] });
}
function p(text) {
  return new Paragraph({ children: [new TextRun({ text })], spacing: { after: 120 } });
}
function bullet(text) {
  return new Paragraph({ numbering: { reference: 'bullets', level: 0 }, children: [new TextRun(text)], spacing: { after: 60 } });
}
function headerRow(cols, widths) {
  return new TableRow({ children: cols.map((c, i) => new TableCell({
    borders: hBorders,
    width: { size: widths[i], type: WidthType.DXA },
    shading: { fill: '1F4E79', type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text: c, bold: true, color: 'FFFFFF', size: 20 })], spacing: { after: 0 } })]
  })) });
}
function dataRow(cols, widths, shade) {
  return new TableRow({ children: cols.map((c, i) => new TableCell({
    borders,
    width: { size: widths[i], type: WidthType.DXA },
    shading: shade ? { fill: 'EBF3FB', type: ShadingType.CLEAR } : undefined,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text: c, size: 20 })], spacing: { after: 0 } })]
  })) });
}

const doc = new Document({
  numbering: {
    config: [{
      reference: 'bullets',
      levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
        style: { paragraph: { indent: { left: 720, hanging: 360 } } } }]
    }]
  },
  styles: {
    default: { document: { run: { font: 'Arial', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 32, bold: true, font: 'Arial', color: '1F4E79' },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 26, bold: true, font: 'Arial', color: '2E75B6' },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } },
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 }
      }
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        children: [new TextRun({ text: 'ООО «АЛИНА ФАРМА» | Система проверки макетов этикеток БАД', color: '888888', size: 18, italics: true })],
        border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: '2E75B6' } }
      })] })
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        children: [
          new TextRun({ text: 'Blueprint v1.0 | Июнь 2026 | Конфиденциально    ', color: '888888', size: 18 }),
          new TextRun({ text: 'Стр. ', color: '888888', size: 18 }),
          new TextRun({ children: [PageNumber.CURRENT], color: '888888', size: 18 }),
        ],
        border: { top: { style: BorderStyle.SINGLE, size: 4, color: '2E75B6' } }
      })] })
    },
    children: [
      new Paragraph({ spacing: { before: 800 } }),
      new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'BLUEPRINT', bold: true, size: 56, color: '1F4E79', font: 'Arial' })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Система проверки макетов этикеток БАД', bold: true, size: 36, color: '2E75B6', font: 'Arial' })] }),
      new Paragraph({ spacing: { before: 200 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Версия 1.0  |  ООО «АЛИНА ФАРМА»  |  Июнь 2026', size: 24, color: '666666', font: 'Arial' })] }),
      new Paragraph({ children: [new PageBreak()] }),

      h(1, '1. Обзор продукта'),
      h(2, '1.1 Концепция'),
      p('Система автоматизированной проверки макетов этикеток — веб-приложение для ООО «АЛИНА ФАРМА», которое помогает специалисту по регистрации продукции выявлять ошибки в макетах этикеток, коробочек и инструкций (вкладышей) перед отправкой в типографию.'),
      p('Принцип «человек в контуре»: система находит и флагирует проблемы, финальное решение о согласовании принимает человек.'),
      h(2, '1.2 Категории продукции'),
      bullet('Биологически активные добавки (БАД)'),
      bullet('Спортивное питание'),
      bullet('Бакалейная продукция'),
      h(2, '1.3 Ключевые метрики успеха'),
      bullet('Сокращение времени проверки одного макета на 40–70%'),
      bullet('Снижение количества ошибок, попадающих в типографию'),
      bullet('Полное соответствие ТР ТС 022/2011, МР 2.3.1.0253-21, Единым санитарным требованиям'),

      h(1, '2. Архитектура системы'),
      h(2, '2.1 Высокоуровневая архитектура'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [2200, 3200, 3626],
        rows: [
          headerRow(['Слой', 'Технология', 'Назначение'], [2200, 3200, 3626]),
          dataRow(['Frontend', 'React 18 + Vite + Tailwind CSS', 'SPA — интерфейс пользователя'], [2200, 3200, 3626]),
          dataRow(['Backend API', 'Python 3.11 + FastAPI + Celery', 'REST API, очередь задач, пайплайн проверок'], [2200, 3200, 3626], true),
          dataRow(['База данных', 'PostgreSQL 15', 'Метаданные, журнал, пользователи'], [2200, 3200, 3626]),
          dataRow(['Файловое хранилище', 'Selectel Object Storage (S3)', 'Макеты, ПЭН, PDF-отчёты'], [2200, 3200, 3626], true),
          dataRow(['Очередь задач', 'Redis + Celery', 'Асинхронная параллельная обработка'], [2200, 3200, 3626]),
          dataRow(['OCR / AI', 'Yandex Vision, ABBYY, OpenAI, Gemini, Claude, Grok', 'Извлечение текста и AI-анализ'], [2200, 3200, 3626], true),
        ]
      }),
      h(2, '2.2 Пайплайн проверки (5 этапов)'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [500, 2200, 3300, 3026],
        rows: [
          headerRow(['№', 'Этап', 'Описание', 'Провайдер'], [500, 2200, 3300, 3026]),
          dataRow(['1', 'Извлечение текста', 'PDF text layer или OCR для растрированных PDF/JPG', 'Yandex Vision / ABBYY / LLM Vision'], [500, 2200, 3300, 3026]),
          dataRow(['2', 'Орфография и стилистика', 'Проверка текста с отраслевым словарём', 'LLM (Claude / GPT / Gemini)'], [500, 2200, 3300, 3026], true),
          dataRow(['3', 'Сверка с ПЭН', 'Толерантное сравнение с эталоном по полям', 'LLM со structured output'], [500, 2200, 3300, 3026]),
          dataRow(['4', 'Нормативный чек-лист', 'ТР ТС 022/2011, МР 2.3.1.0253-21, ЕАЭС-знак', 'LLM + Vision'], [500, 2200, 3300, 3026], true),
          dataRow(['5', 'Генерация отчёта', 'Размеченный PDF + структурированный список', 'Внутренний движок'], [500, 2200, 3300, 3026]),
        ]
      }),

      h(1, '3. Функциональные блоки MVP'),
      h(2, '3.1 Загрузка и управление файлами'),
      bullet('Drag & drop загрузка PDF и JPG (текст в кривых / растрированный — требуется OCR)'),
      bullet('Структурированный эталон ПЭН в формате Word (поля: наименование, состав, дозировки и т.д.)'),
      bullet('Пакетная загрузка через ZIP-архив'),
      bullet('Версионирование: все версии макета и ПЭН сохраняются'),
      bullet('Поддержка многоязычных этикеток (русский + языки стран ЕАЭС)'),
      h(2, '3.2 Модули проверки'),
      bullet('Орфография/стилистика — с отраслевым словарём (INCI, латынь, мг/мкг/МЕ, бренды)'),
      bullet('Сверка с ПЭН — толерантное сравнение, порядок состава, числа и единицы измерения'),
      bullet('Нормативный чек-лист — обязательные элементы по ТР ТС 022/2011 + МР 2.3.1.0253-21'),
      bullet('Layout-анализ — размер шрифта (>=2 мм), контрастность, знак ЕАЭС, штрих-код'),
      bullet('Кросс-проверка комплекта — непротиворечивость между носителями'),
      h(2, '3.3 Результаты и отчётность'),
      bullet('Интерактивный просмотр размеченного PDF (красный/жёлтый/зелёный аннотации)'),
      bullet('Структурированный список расхождений с навигацией к месту ошибки'),
      bullet('Журнал проверок с поиском и фильтрацией'),
      bullet('Дифф версий — side-by-side или unified сравнение'),
      bullet('Экспорт: PDF-отчёт, Excel (таблица расхождений), Word'),
      bullet('Согласование макета — кнопка «Отправить в типографию»'),
      h(2, '3.4 Административная панель'),
      bullet('Управление пользователями (CRUD, роли)'),
      bullet('API-ключи провайдеров (Yandex Vision, ABBYY, OpenAI, Gemini, Claude, Grok) с маскировкой'),
      bullet('Конфигурация пайплайна: выбор провайдера на каждый этап или единый LLM-режим'),
      bullet('Подключение Selectel Object Storage (endpoint, access/secret keys, bucket)'),
      bullet('Системные логи и статистика'),

      h(1, '4. Роли и доступ'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [2500, 6526],
        rows: [
          headerRow(['Роль', 'Возможности'], [2500, 6526]),
          dataRow(['Администратор', 'Все функции + управление пользователями + API-ключи + конфигурация хранилища + системные логи'], [2500, 6526]),
          dataRow(['Специалист по регистрации', 'Загрузка, проверки, результаты, журнал, экспорт, согласование, управление справочниками'], [2500, 6526], true),
        ]
      }),

      h(1, '5. Нефункциональные требования'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [2500, 6526],
        rows: [
          headerRow(['Параметр', 'Требование'], [2500, 6526]),
          dataRow(['Производительность', 'Обработка макета: не более 60-90 сек (гибридный режим), не более 45 сек (единый LLM)'], [2500, 6526]),
          dataRow(['Безопасность', 'RBAC (2 роли), аудит действий, шифрование API-ключей, защита ПЭН'], [2500, 6526], true),
          dataRow(['Хранение данных', 'Локализация в РФ (Selectel), TLS 1.3, соответствие 152-ФЗ'], [2500, 6526]),
          dataRow(['Надёжность', 'Fallback между провайдерами, очередь задач, возможность повтора'], [2500, 6526], true),
          dataRow(['UI/UX', 'React + Tailwind, не более 4 кликов для типового сценария, тёмная/светлая тема'], [2500, 6526]),
        ]
      }),

      h(1, '6. Технологический стек'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [2800, 6226],
        rows: [
          headerRow(['Компонент', 'Технология'], [2800, 6226]),
          dataRow(['Backend', 'Python 3.11 + FastAPI + Uvicorn'], [2800, 6226]),
          dataRow(['Frontend', 'React 18 + Vite + Tailwind CSS + shadcn/ui'], [2800, 6226], true),
          dataRow(['ORM / Миграции', 'SQLAlchemy + Alembic'], [2800, 6226]),
          dataRow(['База данных', 'PostgreSQL 15'], [2800, 6226], true),
          dataRow(['Файловое хранилище', 'Selectel Object Storage (boto3/aiobotocore)'], [2800, 6226]),
          dataRow(['Очередь задач', 'Redis + Celery'], [2800, 6226], true),
          dataRow(['Аутентификация', 'JWT (access + refresh tokens), bcrypt'], [2800, 6226]),
          dataRow(['PDF обработка', 'pdfplumber, PyMuPDF (fitz), pdf2image, Pillow'], [2800, 6226], true),
          dataRow(['Экспорт отчётов', 'ReportLab (PDF), openpyxl (Excel), python-docx (Word)'], [2800, 6226]),
          dataRow(['Контейнеризация', 'Docker + Docker Compose'], [2800, 6226], true),
        ]
      }),

      h(1, '7. Структура директорий проекта'),
      new Paragraph({ children: [new TextRun({ text:
        'alina-pharma-labels-check/\n' +
        '  backend/\n' +
        '    app/\n' +
        '      api/          - FastAPI роутеры\n' +
        '      core/         - Конфигурация, безопасность, JWT\n' +
        '      models/       - SQLAlchemy модели БД\n' +
        '      schemas/      - Pydantic схемы запросов/ответов\n' +
        '      services/     - Бизнес-логика\n' +
        '      pipeline/     - Этапы проверки (OCR, LLM, чек-лист)\n' +
        '      workers/      - Celery задачи\n' +
        '    migrations/     - Alembic миграции\n' +
        '    tests/\n' +
        '  frontend/\n' +
        '    src/\n' +
        '      components/   - UI компоненты\n' +
        '      pages/        - Страницы\n' +
        '      api/          - API клиент (axios)\n' +
        '      store/        - Zustand состояние\n' +
        '    public/\n' +
        '  docker-compose.yml\n' +
        '  docs/',
        font: 'Courier New', size: 18 })] }),

      h(1, '8. Основные экраны'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [3000, 6026],
        rows: [
          headerRow(['Экран', 'Основные элементы'], [3000, 6026]),
          dataRow(['Дашборд', 'Статистика проверок, последние задачи, кнопка «Новая проверка»'], [3000, 6026]),
          dataRow(['Новая проверка', 'Drag & drop зона, выбор ПЭН, категория, кнопка «Запустить»'], [3000, 6026], true),
          dataRow(['Результаты проверки', 'PDF с аннотациями (PDF.js), список замечаний, экспорт'], [3000, 6026]),
          dataRow(['Журнал проверок', 'Таблица с поиском, фильтры, история версий'], [3000, 6026], true),
          dataRow(['Сравнение версий', 'Side-by-side дифф двух версий макета'], [3000, 6026]),
          dataRow(['Справочники', 'Отраслевой словарь, бренды, правила категорий'], [3000, 6026], true),
          dataRow(['Админ-панель', 'API-ключи, конфигурация пайплайна, пользователи, логи'], [3000, 6026]),
        ]
      }),

      h(1, '9. Вне скопа MVP'),
      bullet('Интеграции с 1С, ЭДО, DAM-системами — запланированы на следующие версии'),
      bullet('Автоматический мониторинг почты — только ручная загрузка в MVP'),
      bullet('Уровни критичности замечаний — следующая версия'),
      bullet('Проверка аллергенов и пересчёт % от суточной нормы — не требуется (всё в ПЭН)'),

      new Paragraph({ spacing: { before: 400 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'ООО «АЛИНА ФАРМА»  |  Конфиденциально  |  Blueprint v1.0  |  Июнь 2026', color: '888888', size: 18 })] }),
    ]
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync('Blueprint_v1.0_Система_проверки_этикеток.docx', buf);
  console.log('Blueprint created OK');
}).catch(e => { console.error(e); process.exit(1); });
