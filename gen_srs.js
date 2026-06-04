const { Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell, HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType, LevelFormat, PageBreak, Header, Footer, PageNumber } = require('docx');
const fs = require('fs');

const border = { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' };
const borders = { top: border, bottom: border, left: border, right: border };
const hBorder = { style: BorderStyle.SINGLE, size: 1, color: '2E75B6' };
const hBorders = { top: hBorder, bottom: hBorder, left: hBorder, right: hBorder };

function h1(text) { return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] }); }
function h2(text) { return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] }); }
function h3(text) { return new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(text)] }); }
function p(text) { return new Paragraph({ children: [new TextRun({ text })], spacing: { after: 120 } }); }
function bullet(text) { return new Paragraph({ numbering: { reference: 'bullets', level: 0 }, children: [new TextRun(text)], spacing: { after: 60 } }); }
function numbered(text) { return new Paragraph({ numbering: { reference: 'numbers', level: 0 }, children: [new TextRun(text)], spacing: { after: 60 } }); }
function headerRow(cols, widths) {
  return new TableRow({ children: cols.map((c, i) => new TableCell({
    borders: hBorders, width: { size: widths[i], type: WidthType.DXA },
    shading: { fill: '1F4E79', type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text: c, bold: true, color: 'FFFFFF', size: 20 })], spacing: { after: 0 } })]
  })) });
}
function dataRow(cols, widths, shade) {
  return new TableRow({ children: cols.map((c, i) => new TableCell({
    borders, width: { size: widths[i], type: WidthType.DXA },
    shading: shade ? { fill: 'EBF3FB', type: ShadingType.CLEAR } : undefined,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text: c, size: 20 })], spacing: { after: 0 } })]
  })) });
}

const doc = new Document({
  numbering: {
    config: [
      { reference: 'bullets', levels: [{ level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
      { reference: 'numbers', levels: [{ level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] },
    ]
  },
  styles: {
    default: { document: { run: { font: 'Arial', size: 22 } } },
    paragraphStyles: [
      { id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 32, bold: true, font: 'Arial', color: '1F4E79' },
        paragraph: { spacing: { before: 360, after: 180 }, outlineLevel: 0 } },
      { id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 26, bold: true, font: 'Arial', color: '2E75B6' },
        paragraph: { spacing: { before: 280, after: 120 }, outlineLevel: 1 } },
      { id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, font: 'Arial', color: '404040' },
        paragraph: { spacing: { before: 200, after: 80 }, outlineLevel: 2 } },
    ]
  },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    headers: { default: new Header({ children: [new Paragraph({ children: [new TextRun({ text: 'ООО «АЛИНА ФАРМА» | SRS — Система проверки макетов этикеток БАД | v1.0', color: '888888', size: 18, italics: true })], border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: '2E75B6' } } })] }) },
    footers: { default: new Footer({ children: [new Paragraph({ children: [new TextRun({ text: 'SRS v1.0 | Июнь 2026 | Конфиденциально    ', color: '888888', size: 18 }), new TextRun({ text: 'Стр. ', color: '888888', size: 18 }), new TextRun({ children: [PageNumber.CURRENT], color: '888888', size: 18 })], border: { top: { style: BorderStyle.SINGLE, size: 4, color: '2E75B6' } } })] }) },
    children: [
      // Title page
      new Paragraph({ spacing: { before: 600 } }),
      new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'ТЕХНИЧЕСКОЕ ЗАДАНИЕ (SRS)', bold: true, size: 52, color: '1F4E79', font: 'Arial' })] }),
      new Paragraph({ spacing: { before: 120 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Система автоматизированной проверки макетов этикеток', bold: true, size: 34, color: '2E75B6', font: 'Arial' })] }),
      new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'БАД, спортивного питания и бакалейной продукции', bold: true, size: 28, color: '2E75B6', font: 'Arial' })] }),
      new Paragraph({ spacing: { before: 300 }, alignment: AlignmentType.CENTER }),
      new Table({
        width: { size: 6000, type: WidthType.DXA },
        columnWidths: [2500, 3500],
        rows: [
          dataRow(['Заказчик:', 'ООО «АЛИНА ФАРМА»'], [2500, 3500]),
          dataRow(['Версия документа:', '1.0'], [2500, 3500], true),
          dataRow(['Дата:', 'Июнь 2026'], [2500, 3500]),
          dataRow(['Статус:', 'На согласование'], [2500, 3500], true),
          dataRow(['Язык интерфейса:', 'Русский'], [2500, 3500]),
        ]
      }),
      new Paragraph({ children: [new PageBreak()] }),

      // 1
      h1('1. Введение'),
      h2('1.1 Цели документа'),
      p('Настоящий документ является Техническим заданием (Software Requirements Specification, SRS) на разработку системы автоматизированной проверки макетов этикеток, коробочек и инструкций (вкладышей) для продукции ООО «АЛИНА ФАРМА».'),
      p('Документ описывает функциональные и нефункциональные требования к системе, ограничения, модели данных, API-контракты и критерии приёмки. Служит основой для проектирования, разработки и тестирования.'),
      h2('1.2 Область применения'),
      p('Система предназначена для проверки макетов трёх категорий продукции:'),
      bullet('Биологически активные добавки (БАД) — требования ТР ТС 022/2011, МР 2.3.1.0253-21'),
      bullet('Спортивное питание — требования ТР ТС 022/2011 (с учётом специфики категории)'),
      bullet('Бакалейная продукция — Единые санитарно-эпидемиологические требования ЕАЭС'),
      h2('1.3 Определения и сокращения'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [2000, 7026],
        rows: [
          headerRow(['Термин', 'Определение'], [2000, 7026]),
          dataRow(['БАД', 'Биологически активная добавка к пище'], [2000, 7026]),
          dataRow(['ПЭН', 'Программный эталон наименования — структурированный документ Word с утверждёнными данными о продукте (состав, дозировки, реквизиты и т.д.)'], [2000, 7026], true),
          dataRow(['OCR', 'Optical Character Recognition — распознавание текста на изображениях'], [2000, 7026]),
          dataRow(['LLM', 'Large Language Model — большая языковая модель (GPT, Gemini, Claude и др.)'], [2000, 7026], true),
          dataRow(['ЕАЭС', 'Евразийский экономический союз'], [2000, 7026]),
          dataRow(['ТР ТС', 'Технический регламент Таможенного союза'], [2000, 7026], true),
          dataRow(['МР', 'Методические рекомендации Роспотребнадзора'], [2000, 7026]),
          dataRow(['СГР', 'Свидетельство о государственной регистрации'], [2000, 7026], true),
          dataRow(['ТУ', 'Технические условия'], [2000, 7026]),
          dataRow(['INCI', 'International Nomenclature Cosmetic Ingredients — международная номенклатура ингредиентов'], [2000, 7026], true),
          dataRow(['RBAC', 'Role-Based Access Control — управление доступом на основе ролей'], [2000, 7026]),
          dataRow(['JWT', 'JSON Web Token — токен аутентификации'], [2000, 7026], true),
          dataRow(['S3', 'Amazon S3-совместимый протокол объектного хранилища'], [2000, 7026]),
        ]
      }),
      h2('1.4 Ссылки на нормативные документы'),
      bullet('ТР ТС 022/2011 «Пищевая продукция в части её маркировки» — Приложение 2'),
      bullet('МР 2.3.1.0253-21 «Нормы физиологических потребностей в энергии и пищевых веществах» — Раздел 5.3, Таблица 21'),
      bullet('Единые санитарно-эпидемиологические и гигиенические требования ЕАЭС — Глава II, Раздел 1, Приложение 5'),
      bullet('Федеральный закон № 152-ФЗ «О персональных данных»'),
      new Paragraph({ children: [new PageBreak()] }),

      // 2
      h1('2. Общее описание системы'),
      h2('2.1 Контекст системы'),
      p('Система является самостоятельным веб-приложением. В MVP не требует интеграции с внешними корпоративными системами (1С, ЭДО, DAM). Взаимодействует с внешними API-сервисами OCR и LLM для выполнения проверок. Все данные хранятся на территории РФ.'),
      h2('2.2 Функции системы (верхний уровень)'),
      bullet('Загрузка и хранение макетов и эталонов ПЭН'),
      bullet('Автоматический многоэтапный анализ макетов (OCR + 4 модуля проверки)'),
      bullet('Генерация структурированных отчётов с аннотированным PDF'),
      bullet('Ведение журнала проверок и версионирование'),
      bullet('Гибкая настройка провайдеров AI/OCR администратором'),
      bullet('Экспорт результатов (PDF, Excel, Word)'),
      bullet('Согласование макета для отправки в типографию'),
      h2('2.3 Характеристики пользователей'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [2500, 6526],
        rows: [
          headerRow(['Пользователь', 'Характеристики'], [2500, 6526]),
          dataRow(['Специалист по регистрации', 'Основной пользователь. Работает с системой ежедневно. Хорошо знает нормативные требования к маркировке. Не обязан быть технически квалифицированным. Использует все производственные функции.'], [2500, 6526]),
          dataRow(['Администратор', 'Технически квалифицированный пользователь. Настраивает систему. Управляет пользователями и API-ключами. Обычно 1 человек на организацию.'], [2500, 6526], true),
        ]
      }),
      h2('2.4 Ограничения'),
      bullet('Язык интерфейса — только русский'),
      bullet('Все данные должны храниться на серверах в РФ (требование 152-ФЗ)'),
      bullet('Шифрование API-ключей обязательно (хранятся в зашифрованном виде)'),
      bullet('Данные о рецептурах (ПЭН) являются коммерческой тайной — строгий контроль доступа'),
      bullet('Внешние API-запросы к LLM/OCR разрешены (данные макетов передаются провайдерам по выбору администратора)'),
      new Paragraph({ children: [new PageBreak()] }),

      // 3
      h1('3. Функциональные требования'),
      h2('3.1 Аутентификация и авторизация'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [1200, 5826, 1200, 800],
        rows: [
          headerRow(['ID', 'Требование', 'Приоритет', 'Версия'], [1200, 5826, 1200, 800]),
          dataRow(['FR-AUTH-01', 'Регистрация пользователей только администратором (самостоятельная регистрация отсутствует)', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-AUTH-02', 'Аутентификация по логину (email) и паролю с выдачей JWT access + refresh токенов', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-AUTH-03', 'Access token TTL: 15 минут. Refresh token TTL: 7 дней. Автоматическое обновление.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-AUTH-04', 'Хеширование паролей: bcrypt, cost factor >= 12', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-AUTH-05', 'RBAC: две роли — admin и specialist. Права проверяются на уровне API.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-AUTH-06', 'Audit log: все действия пользователей (загрузка, запуск проверки, согласование) записываются с timestamp, user_id, action, resource_id', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
        ]
      }),

      h2('3.2 Загрузка файлов'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [1200, 5826, 1200, 800],
        rows: [
          headerRow(['ID', 'Требование', 'Приоритет', 'Версия'], [1200, 5826, 1200, 800]),
          dataRow(['FR-UPL-01', 'Загрузка макетов: форматы PDF и JPG/JPEG. Максимальный размер файла: 100 МБ.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-UPL-02', 'Загрузка ПЭН: формат DOCX (Word). Максимальный размер: 20 МБ.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-UPL-03', 'Веб-интерфейс drag & drop + multi-select с отображением списка файлов и прогресса загрузки.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-UPL-04', 'Пакетная загрузка через ZIP-архив: система автоматически распаковывает и сопоставляет файлы (по имени или интерактивно).', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-UPL-05', 'Версионирование: при повторной загрузке файла с тем же именем/продуктом создаётся новая версия, предыдущая сохраняется.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-UPL-06', 'Хранение файлов в Selectel Object Storage. Метаданные (имя, тип, версия, user_id, timestamp) в PostgreSQL.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-UPL-07', 'Поддержка загрузки комплекта (этикетка + коробочка + инструкция) как единой группы.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
        ]
      }),

      h2('3.3 Пайплайн проверки'),
      h3('3.3.1 Общие требования к пайплайну'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [1200, 5826, 1200, 800],
        rows: [
          headerRow(['ID', 'Требование', 'Приоритет', 'Версия'], [1200, 5826, 1200, 800]),
          dataRow(['FR-PIP-01', 'Пайплайн запускается асинхронно через Celery. Результаты доступны по polling или WebSocket.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-PIP-02', 'Гибридный режим: провайдер каждого из 5 этапов настраивается независимо в админ-панели.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-PIP-03', 'Единый LLM-режим: одна выбранная модель выполняет все этапы. Переключение в админ-панели.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-PIP-04', 'При ошибке провайдера: автоматический retry (3 попытки с backoff), затем fallback или статус FAILED.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-PIP-05', 'Статусы задачи: PENDING, RUNNING, COMPLETED, FAILED, CANCELLED. Доступны через API.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-PIP-06', 'Возможность отмены запущенной задачи и повторного запуска.', 'Средний', 'MVP'], [1200, 5826, 1200, 800], true),
        ]
      }),
      h3('3.3.2 Этап 1: Извлечение текста (OCR)'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [1200, 5826, 1200, 800],
        rows: [
          headerRow(['ID', 'Требование', 'Приоритет', 'Версия'], [1200, 5826, 1200, 800]),
          dataRow(['FR-OCR-01', 'Для PDF: сначала попытка извлечения text layer (pdfplumber). Если покрытие < 80% страницы — запуск OCR.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-OCR-02', 'Для JPG и PDF с растрированным текстом: обязательный OCR через выбранного провайдера.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-OCR-03', 'Поддерживаемые OCR-провайдеры: Yandex Vision API, ABBYY Cloud OCR SDK, OpenAI GPT-4o Vision, Google Gemini Vision, Anthropic Claude Vision.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-OCR-04', 'OCR должен поддерживать русский язык, кириллицу, латиницу, цифры, спецсимволы (мг, мкг, МЕ, %).', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-OCR-05', 'Сохранение координат текстовых блоков для последующей аннотации PDF.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-OCR-06', 'Поддержка многоязычных этикеток: извлечение текстов на русском и языках стран ЕАЭС (казахский, белорусский, армянский, киргизский).', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
        ]
      }),
      h3('3.3.3 Этап 2: Орфография и стилистика'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [1200, 5826, 1200, 800],
        rows: [
          headerRow(['ID', 'Требование', 'Приоритет', 'Версия'], [1200, 5826, 1200, 800]),
          dataRow(['FR-ORTH-01', 'Проверка орфографии на русском языке и латинице (адреса иностранных производителей).', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-ORTH-02', 'Использование отраслевого словаря: ингредиенты (INCI-номенклатура), латинские наименования, сокращения (мг, мкг, МЕ, г, мл). Слова из словаря не помечаются как ошибки.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-ORTH-03', 'Белый список брендов и товарных знаков. Пользователь может добавлять/удалять записи.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-ORTH-04', 'Выявление стилистических проблем: тавтология, типографика (прямые кавычки вместо «ёлочек», неправильные тире), неразрывные пробелы.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-ORTH-05', 'Выявление ошибок переносов и «висячих» строк в вёрстке.', 'Средний', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-ORTH-06', 'Каждое замечание содержит: текст ошибки, предлагаемое исправление, координаты на макете.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
        ]
      }),
      h3('3.3.4 Этап 3: Сверка с ПЭН'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [1200, 5826, 1200, 800],
        rows: [
          headerRow(['ID', 'Требование', 'Приоритет', 'Версия'], [1200, 5826, 1200, 800]),
          dataRow(['FR-PEN-01', 'Парсинг структурированного ПЭН (DOCX): извлечение полей по заголовкам (наименование, состав, дозировки, масса нетто, реквизиты производителя, № и дата СГР, № ТУ и др.).', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-PEN-02', 'Толерантное совпадение: без учёта регистра, лишних пробелов, переносов строк.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-PEN-03', 'Сигнализация о вариантах записи: «мг» vs «миллиграмм», «вит. С» vs «витамин С», форматы дат (DD.MM.YYYY vs DD/MM/YYYY) и т.д.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-PEN-04', 'Проверка порядка компонентов состава по убыванию массовой доли согласно ПЭН.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-PEN-05', 'Сверка числовых значений и единиц измерения (дозировки, масса нетто, количество в упаковке). Любое расхождение сигнализируется.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-PEN-06', 'Дословная сверка обязательной фразы «БАД. Не является лекарственным средством» согласно тексту ПЭН.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-PEN-07', 'Проверка наличия и корректности реквизитов производителя: юридический адрес, адрес производства, контакты для претензий, № ТУ, № и дата СГР.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-PEN-08', 'Проверка соответствия формы выпуска (капсулы, таблетки, порошки, жидкости, мармелад жевательный) правилам маркировки категории.', 'Средний', 'MVP'], [1200, 5826, 1200, 800], true),
        ]
      }),
      h3('3.3.5 Этап 4: Нормативный чек-лист и layout-анализ'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [1200, 5826, 1200, 800],
        rows: [
          headerRow(['ID', 'Требование', 'Приоритет', 'Версия'], [1200, 5826, 1200, 800]),
          dataRow(['FR-REG-01', 'Чек-лист на соответствие ТР ТС 022/2011 Приложение 2: наличие всех обязательных элементов маркировки.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-REG-02', 'Чек-лист МР 2.3.1.0253-21 Раздел 5.3, Таблица 21: форматы указания нутриентов.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-REG-03', 'Чек-лист Единых санитарно-эпидемиологических требований ЕАЭС Глава II, Раздел 1, Приложение 5.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-REG-04', 'Проверка наличия знака обращения ЕАЭС (ЕАС) — обязательно.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-REG-05', 'Проверка наличия штрих-кода и петли Мёбиуса (знак переработки).', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-REG-06', 'Layout-анализ: оценка размера шрифта для обязательных элементов (наименование, дата изготовления, срок годности) — требование >= 2 мм. Реализуется через vision-провайдера с калибровкой.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-REG-07', 'Layout-анализ: оценка контрастности текста к фону (базовая проверка читаемости).', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-REG-08', 'Чек-лист настраиваемый: администратор и специалист могут обновлять правила через интерфейс справочников.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
        ]
      }),
      h3('3.3.6 Этап 5: Генерация отчёта'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [1200, 5826, 1200, 800],
        rows: [
          headerRow(['ID', 'Требование', 'Приоритет', 'Версия'], [1200, 5826, 1200, 800]),
          dataRow(['FR-REP-01', 'Генерация аннотированного PDF: поверх оригинального макета накладываются цветные прямоугольники — красный (ошибка), жёлтый (предупреждение), зелёный (ок).', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-REP-02', 'Структурированный список расхождений: тип, описание, расположение, источник (какой модуль обнаружил), предлагаемое действие.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-REP-03', 'Клик по замечанию в списке — прокрутка и подсветка соответствующего места в PDF.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-REP-04', 'Экспорт в PDF: полный отчёт с аннотациями и списком замечаний.', 'Средний', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-REP-05', 'Экспорт в Excel: таблица расхождений (колонки: №, тип, описание, место, статус).', 'Средний', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-REP-06', 'Экспорт в Word: структурированный отчёт.', 'Средний', 'MVP'], [1200, 5826, 1200, 800], true),
        ]
      }),

      h2('3.4 Журнал, версионирование и дифф'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [1200, 5826, 1200, 800],
        rows: [
          headerRow(['ID', 'Требование', 'Приоритет', 'Версия'], [1200, 5826, 1200, 800]),
          dataRow(['FR-LOG-01', 'Журнал всех проверок: поиск по наименованию продукта, дате, статусу, пользователю.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-LOG-02', 'Версионирование: каждая загрузка нового файла для того же продукта создаёт новую версию. Все версии доступны в истории.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-LOG-03', 'Дифф версий (текстовый): визуализация добавленных/удалённых/изменённых текстовых блоков между двумя версиями.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-LOG-04', 'Дифф версий (визуальный): side-by-side сравнение двух версий макета.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-LOG-05', 'Согласование макета: кнопка «Согласовать для типографии» — фиксирует версию, статус, пользователя и timestamp.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
        ]
      }),

      h2('3.5 Справочники'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [1200, 5826, 1200, 800],
        rows: [
          headerRow(['ID', 'Требование', 'Приоритет', 'Версия'], [1200, 5826, 1200, 800]),
          dataRow(['FR-REF-01', 'Отраслевой словарь: CRUD-операции. Категории: INCI-ингредиенты, латинские наименования, сокращения, спецсимволы. Доступен специалисту.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-REF-02', 'Белый список брендов и ТЗ: CRUD. Доступен специалисту.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-REF-03', 'Правила категорий продукции: настройка специфики проверок для БАД, Спортпита, Бакалеи. Доступен специалисту.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-REF-04', 'Нормативный чек-лист: возможность добавить/отключить/изменить пункты. Доступен специалисту.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-REF-05', 'Настройка tolerance: порог допустимого расхождения для числовых значений (например, ±0.1%). Доступен специалисту.', 'Средний', 'MVP'], [1200, 5826, 1200, 800]),
        ]
      }),

      h2('3.6 Административная панель'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [1200, 5826, 1200, 800],
        rows: [
          headerRow(['ID', 'Требование', 'Приоритет', 'Версия'], [1200, 5826, 1200, 800]),
          dataRow(['FR-ADM-01', 'Управление пользователями: создание, редактирование, блокировка, удаление. Назначение ролей.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-ADM-02', 'Управление API-ключами провайдеров: Yandex Vision, ABBYY, OpenAI, Google Gemini, Anthropic Claude, xAI Grok. Поля с маскировкой, кнопка «Проверить подключение».', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-ADM-03', 'Конфигурация пайплайна: выпадающие списки для назначения провайдера на каждый из 4 этапов. Переключатель «Гибридный / Единый LLM».', 'Высокий', 'MVP'], [1200, 5826, 1200, 800]),
          dataRow(['FR-ADM-04', 'Настройка Selectel Object Storage: endpoint, access key, secret key, bucket name, регион. Кнопка проверки подключения.', 'Высокий', 'MVP'], [1200, 5826, 1200, 800], true),
          dataRow(['FR-ADM-05', 'Просмотр системных логов и базовой статистики (количество проверок за период, ошибки).', 'Средний', 'MVP'], [1200, 5826, 1200, 800]),
        ]
      }),
      new Paragraph({ children: [new PageBreak()] }),

      // 4
      h1('4. Нефункциональные требования'),
      h2('4.1 Производительность'),
      bullet('Обработка типичного макета (PDF/JPG + ПЭН) в гибридном режиме: не более 90 секунд от запуска до готового результата.'),
      bullet('В едином LLM-режиме: не более 45 секунд.'),
      bullet('Пакетная обработка 10–20 файлов: параллельная обработка через Celery, линейное масштабирование.'),
      bullet('Время отклика API (не считая AI-обработку): не более 500 мс для 95-го процентиля.'),
      bullet('Поддержка не менее 10 одновременных пользователей в MVP.'),
      h2('4.2 Безопасность'),
      bullet('Все соединения: HTTPS (TLS 1.3).'),
      bullet('Хранение паролей: bcrypt, cost factor >= 12.'),
      bullet('API-ключи провайдеров: хранятся зашифрованными (AES-256) в БД, в UI отображаются маскированными.'),
      bullet('RBAC: права проверяются на уровне каждого API-эндпоинта.'),
      bullet('Audit log: все действия пользователей с привязкой к user_id, IP, timestamp.'),
      bullet('Защита от CSRF, XSS, SQL-инъекций (параметризованные запросы, Content Security Policy).'),
      bullet('Файлы ПЭН: доступны только авторизованным пользователям, ссылки на S3 — presigned URLs с TTL 1 час.'),
      h2('4.3 Соответствие требованиям 152-ФЗ'),
      bullet('Все данные (файлы, БД, логи) хранятся исключительно на серверах в Российской Федерации.'),
      bullet('Провайдер хранилища: Selectel (ЦОД в РФ).'),
      bullet('Передача персональных данных за рубеж отсутствует (имена пользователей не передаются в LLM).'),
      bullet('Согласие на обработку персональных данных фиксируется при создании учётной записи.'),
      h2('4.4 Надёжность'),
      bullet('Время доступности системы (uptime): не менее 99% в рабочее время (пн–пт, 8:00–20:00 МСК).'),
      bullet('Автоматический retry при ошибках OCR/LLM: 3 попытки с экспоненциальным backoff.'),
      bullet('При исчерпании retry: задача переводится в статус FAILED, пользователь уведомляется.'),
      bullet('Возможность ручного повтора задачи из журнала.'),
      h2('4.5 Usability'),
      bullet('Стандартный сценарий (загрузить → выбрать ПЭН → запустить → просмотреть) — не более 4 кликов.'),
      bullet('Поддержка drag & drop, multi-select, ZIP.'),
      bullet('Прогресс-бары для длительных операций (OCR, AI-проверки).'),
      bullet('Светлая и тёмная тема, responsive для планшетов.'),
      bullet('Keyboard-friendly навигация, ARIA-атрибуты.'),
      new Paragraph({ children: [new PageBreak()] }),

      // 5
      h1('5. Модель данных'),
      h2('5.1 Основные сущности'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [2200, 6826],
        rows: [
          headerRow(['Таблица', 'Ключевые поля'], [2200, 6826]),
          dataRow(['users', 'id, email, password_hash, role (admin/specialist), is_active, created_at, last_login'], [2200, 6826]),
          dataRow(['products', 'id, name, category (bad/sport/grocery), created_by, created_at'], [2200, 6826], true),
          dataRow(['mockups', 'id, product_id, version, file_type (pdf/jpg), s3_key, original_name, uploaded_by, created_at'], [2200, 6826]),
          dataRow(['pen_documents', 'id, product_id, version, s3_key, parsed_fields (JSONB), uploaded_by, created_at'], [2200, 6826], true),
          dataRow(['check_tasks', 'id, mockup_id, pen_id, status, mode (hybrid/unified), pipeline_config (JSONB), started_at, completed_at, error'], [2200, 6826]),
          dataRow(['check_results', 'id, task_id, stage (ocr/spelling/pen/regulatory/report), issues (JSONB), annotated_pdf_s3_key, created_at'], [2200, 6826], true),
          dataRow(['issues', 'id, result_id, type (error/warning/info), module, description, suggestion, bbox (JSONB), status (open/resolved)'], [2200, 6826]),
          dataRow(['audit_log', 'id, user_id, action, resource_type, resource_id, ip_address, created_at'], [2200, 6826], true),
          dataRow(['dictionary_entries', 'id, term, category, added_by, created_at'], [2200, 6826]),
          dataRow(['brand_whitelist', 'id, brand_name, added_by, created_at'], [2200, 6826], true),
          dataRow(['system_config', 'key, value (encrypted for api_keys), updated_by, updated_at'], [2200, 6826]),
        ]
      }),
      h2('5.2 Структура parsed_fields ПЭН (JSONB)'),
      new Paragraph({ children: [new TextRun({ text:
        '{\n' +
        '  "product_name": "string",\n' +
        '  "product_category": "bad|sport|grocery",\n' +
        '  "dosage_form": "капсулы|таблетки|порошок|жидкость|...",\n' +
        '  "net_weight": "string",\n' +
        '  "serving_size": "string",\n' +
        '  "servings_per_pack": "string",\n' +
        '  "composition": [{"name": "string", "amount": "string", "unit": "string"}],\n' +
        '  "bad_disclaimer": "string",\n' +
        '  "manufacturer": {"legal_name": "string", "legal_address": "string", "production_address": "string", "complaints_contact": "string"},\n' +
        '  "sgr_number": "string",\n' +
        '  "sgr_date": "string",\n' +
        '  "tu_number": "string",\n' +
        '  "shelf_life": "string",\n' +
        '  "storage_conditions": "string",\n' +
        '  "eaeu_mark_required": true\n' +
        '}',
        font: 'Courier New', size: 18 })] }),
      new Paragraph({ children: [new PageBreak()] }),

      // 6
      h1('6. API-контракт (REST)'),
      h2('6.1 Базовый URL и аутентификация'),
      p('Базовый URL: /api/v1/'),
      p('Аутентификация: Bearer JWT в заголовке Authorization. Все эндпоинты (кроме /auth/*) требуют токен.'),
      h2('6.2 Эндпоинты'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [1000, 2400, 3626, 2000],
        rows: [
          headerRow(['Метод', 'URL', 'Описание', 'Роль'], [1000, 2400, 3626, 2000]),
          dataRow(['POST', '/auth/login', 'Вход — возвращает access+refresh токены', 'Все'], [1000, 2400, 3626, 2000]),
          dataRow(['POST', '/auth/refresh', 'Обновление access токена', 'Все'], [1000, 2400, 3626, 2000], true),
          dataRow(['POST', '/auth/logout', 'Инвалидация refresh токена', 'Все'], [1000, 2400, 3626, 2000]),
          dataRow(['GET', '/users', 'Список пользователей', 'admin'], [1000, 2400, 3626, 2000], true),
          dataRow(['POST', '/users', 'Создание пользователя', 'admin'], [1000, 2400, 3626, 2000]),
          dataRow(['PUT', '/users/{id}', 'Обновление пользователя', 'admin'], [1000, 2400, 3626, 2000], true),
          dataRow(['DELETE', '/users/{id}', 'Удаление / блокировка пользователя', 'admin'], [1000, 2400, 3626, 2000]),
          dataRow(['POST', '/uploads/mockup', 'Загрузка макета (PDF/JPG)', 'specialist+'], [1000, 2400, 3626, 2000], true),
          dataRow(['POST', '/uploads/pen', 'Загрузка ПЭН (DOCX)', 'specialist+'], [1000, 2400, 3626, 2000]),
          dataRow(['POST', '/uploads/zip', 'Пакетная загрузка ZIP', 'specialist+'], [1000, 2400, 3626, 2000], true),
          dataRow(['GET', '/products', 'Список продуктов с пагинацией и фильтрами', 'specialist+'], [1000, 2400, 3626, 2000]),
          dataRow(['GET', '/products/{id}/mockups', 'Версии макета продукта', 'specialist+'], [1000, 2400, 3626, 2000], true),
          dataRow(['POST', '/checks', 'Запуск новой проверки (mockup_id, pen_id)', 'specialist+'], [1000, 2400, 3626, 2000]),
          dataRow(['GET', '/checks/{id}', 'Статус и результат проверки', 'specialist+'], [1000, 2400, 3626, 2000], true),
          dataRow(['GET', '/checks/{id}/issues', 'Список замечаний проверки', 'specialist+'], [1000, 2400, 3626, 2000]),
          dataRow(['GET', '/checks/{id}/report/pdf', 'Скачать аннотированный PDF', 'specialist+'], [1000, 2400, 3626, 2000], true),
          dataRow(['GET', '/checks/{id}/export/excel', 'Экспорт расхождений в Excel', 'specialist+'], [1000, 2400, 3626, 2000]),
          dataRow(['POST', '/checks/{id}/approve', 'Согласовать макет для типографии', 'specialist+'], [1000, 2400, 3626, 2000], true),
          dataRow(['GET', '/checks/history', 'Журнал проверок с поиском/фильтрами', 'specialist+'], [1000, 2400, 3626, 2000]),
          dataRow(['GET', '/diff/{mockup_id_a}/{mockup_id_b}', 'Текстовый дифф двух версий', 'specialist+'], [1000, 2400, 3626, 2000], true),
          dataRow(['GET/POST/PUT/DELETE', '/references/dictionary', 'CRUD отраслевого словаря', 'specialist+'], [1000, 2400, 3626, 2000]),
          dataRow(['GET/POST/DELETE', '/references/brands', 'CRUD белого списка брендов', 'specialist+'], [1000, 2400, 3626, 2000], true),
          dataRow(['GET/PUT', '/admin/config', 'Настройки системы (API-ключи, пайплайн, S3)', 'admin'], [1000, 2400, 3626, 2000]),
          dataRow(['POST', '/admin/config/test-connection', 'Проверить подключение к провайдеру', 'admin'], [1000, 2400, 3626, 2000], true),
          dataRow(['GET', '/admin/logs', 'Системные логи и статистика', 'admin'], [1000, 2400, 3626, 2000]),
        ]
      }),
      new Paragraph({ children: [new PageBreak()] }),

      // 7
      h1('7. Интеграции с внешними сервисами'),
      h2('7.1 Поддерживаемые провайдеры'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [2200, 2400, 4426],
        rows: [
          headerRow(['Провайдер', 'Применение', 'Метод аутентификации'], [2200, 2400, 4426]),
          dataRow(['Yandex Vision API', 'OCR', 'IAM-токен или API-ключ Yandex Cloud'], [2200, 2400, 4426]),
          dataRow(['ABBYY Cloud OCR SDK', 'OCR (enterprise)', 'Application ID + Password'], [2200, 2400, 4426], true),
          dataRow(['OpenAI API (GPT-4o)', 'OCR Vision + LLM', 'Bearer API Key'], [2200, 2400, 4426]),
          dataRow(['Google Gemini API', 'OCR Vision + LLM', 'API Key'], [2200, 2400, 4426], true),
          dataRow(['Anthropic Claude API', 'LLM (structured output)', 'x-api-key header'], [2200, 2400, 4426]),
          dataRow(['xAI Grok API', 'LLM', 'Bearer API Key (OpenAI-compatible)'], [2200, 2400, 4426], true),
          dataRow(['Selectel Object Storage', 'Хранилище файлов (S3)', 'Access Key + Secret Key'], [2200, 2400, 4426]),
        ]
      }),
      h2('7.2 Абстрактный интерфейс провайдера'),
      p('Все OCR и LLM-провайдеры реализуют единый интерфейс (Python ABC), что позволяет легко добавлять новых и переключаться без изменения кода пайплайна:'),
      new Paragraph({ children: [new TextRun({ text:
        'class BaseOCRProvider(ABC):\n' +
        '    async def extract_text(self, image_bytes: bytes, lang: str) -> OCRResult\n' +
        '    async def test_connection(self) -> bool\n\n' +
        'class BaseLLMProvider(ABC):\n' +
        '    async def check_spelling(self, text: str, dictionary: list) -> SpellingResult\n' +
        '    async def compare_with_pen(self, ocr_text: str, pen_fields: dict) -> PENResult\n' +
        '    async def check_regulatory(self, ocr_text: str, category: str) -> RegulatoryResult\n' +
        '    async def analyze_layout(self, image_bytes: bytes) -> LayoutResult\n' +
        '    async def test_connection(self) -> bool',
        font: 'Courier New', size: 18 })] }),
      new Paragraph({ children: [new PageBreak()] }),

      // 8
      h1('8. Требования к UI/UX'),
      h2('8.1 Дизайн-принципы'),
      bullet('Принципы Nielsen Norman Group: видимость статуса системы, контроль пользователя, предотвращение ошибок, эффективность, минималистичный дизайн.'),
      bullet('Минимальное количество кликов: стандартный сценарий <= 4 кликов.'),
      bullet('Немедленная визуальная обратная связь на все действия пользователя.'),
      bullet('Прогресс-бары для операций дольше 2 секунд.'),
      h2('8.2 Цветовая схема замечаний'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [2000, 2000, 5026],
        rows: [
          headerRow(['Цвет', 'Тип', 'Описание'], [2000, 2000, 5026]),
          dataRow(['Красный (#E53E3E)', 'Ошибка', 'Критическое несоответствие: расхождение с ПЭН, нарушение обязательного требования'], [2000, 2000, 5026]),
          dataRow(['Жёлтый (#D69E2E)', 'Предупреждение', 'Потенциальная проблема: стилистика, вариант написания, рекомендуемое'], [2000, 2000, 5026], true),
          dataRow(['Зелёный (#38A169)', 'ОК', 'Элемент проверен и соответствует требованиям'], [2000, 2000, 5026]),
        ]
      }),
      h2('8.3 Ключевые UX-требования'),
      bullet('PDF просмотр: встроенный viewer (PDF.js) с поддержкой аннотаций, масштабирования, навигации по страницам.'),
      bullet('Клик по замечанию в списке — плавная прокрутка к соответствующей аннотации в PDF.'),
      bullet('Дифф версий: side-by-side или unified вид (переключатель), подсветка изменений.'),
      bullet('Онбординг: встроенный тур для новых пользователей, контекстная справка (tooltips).'),
      bullet('Светлая и тёмная темы. Responsive для планшетов (iPad и аналоги).'),
      bullet('Keyboard shortcuts: пробел = следующее замечание, Enter = открыть детали, Esc = закрыть панель.'),
      new Paragraph({ children: [new PageBreak()] }),

      // 9
      h1('9. Требования к инфраструктуре'),
      h2('9.1 Docker Compose (MVP / разработка)'),
      new Paragraph({ children: [new TextRun({ text:
        'services:\n' +
        '  postgres:    PostgreSQL 15\n' +
        '  redis:       Redis 7 (брокер Celery)\n' +
        '  backend:     FastAPI + Uvicorn\n' +
        '  worker:      Celery worker (обработка задач)\n' +
        '  frontend:    Vite dev server / nginx (prod)\n' +
        '  flower:      Celery Flower (мониторинг очереди, dev)',
        font: 'Courier New', size: 18 })] }),
      h2('9.2 Переменные окружения (backend)'),
      new Paragraph({ children: [new TextRun({ text:
        'DATABASE_URL=postgresql://user:pass@postgres:5432/alina_pharma\n' +
        'REDIS_URL=redis://redis:6379/0\n' +
        'SECRET_KEY=<random 64 bytes hex>\n' +
        'ENCRYPTION_KEY=<AES-256 key for API keys>\n' +
        'S3_ENDPOINT_URL=https://s3.selectel.ru\n' +
        'S3_ACCESS_KEY=<from admin settings>\n' +
        'S3_SECRET_KEY=<from admin settings>\n' +
        'S3_BUCKET=<from admin settings>\n' +
        'CORS_ORIGINS=http://localhost:5173,https://yourdomain.ru',
        font: 'Courier New', size: 18 })] }),
      new Paragraph({ children: [new PageBreak()] }),

      // 10
      h1('10. Критерии приёмки MVP'),
      new Table({
        width: { size: 9026, type: WidthType.DXA },
        columnWidths: [500, 5526, 3000],
        rows: [
          headerRow(['№', 'Критерий', 'Проверка'], [500, 5526, 3000]),
          dataRow(['1', 'Загрузка PDF с растрированным текстом — успешное извлечение текста через OCR', 'Функциональный тест'], [500, 5526, 3000]),
          dataRow(['2', 'Загрузка ПЭН в формате DOCX — успешный парсинг всех полей', 'Функциональный тест'], [500, 5526, 3000], true),
          dataRow(['3', 'Сверка макета с ПЭН — система выявляет намеренно внесённые расхождения в числах, составе, реквизитах', 'Тест на реальных данных'], [500, 5526, 3000]),
          dataRow(['4', 'Нормативный чек-лист — система обнаруживает отсутствие знака ЕАЭС и штрих-кода', 'Функциональный тест'], [500, 5526, 3000], true),
          dataRow(['5', 'Генерация аннотированного PDF с цветными маркерами', 'Визуальная проверка'], [500, 5526, 3000]),
          dataRow(['6', 'Экспорт в Excel — корректная таблица расхождений', 'Функциональный тест'], [500, 5526, 3000], true),
          dataRow(['7', 'Время обработки типичного макета <= 90 секунд', 'Performance тест'], [500, 5526, 3000]),
          dataRow(['8', 'RBAC: специалист не может открыть страницу управления пользователями', 'Тест безопасности'], [500, 5526, 3000], true),
          dataRow(['9', 'API-ключи хранятся зашифрованными, не видны в API-ответах', 'Тест безопасности'], [500, 5526, 3000]),
          dataRow(['10', 'Пакетная загрузка ZIP из 5 комплектов — корректная обработка каждого', 'Функциональный тест'], [500, 5526, 3000], true),
        ]
      }),

      new Paragraph({ spacing: { before: 400 }, alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'ООО «АЛИНА ФАРМА»  |  Конфиденциально  |  SRS v1.0  |  Июнь 2026', color: '888888', size: 18 })] }),
    ]
  }]
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync('SRS_v1.0_Система_проверки_этикеток.docx', buf);
  console.log('SRS created OK');
}).catch(e => { console.error(e); process.exit(1); });
