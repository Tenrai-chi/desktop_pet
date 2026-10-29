html_reference = """
        <html>
        <head>
        <style>
            body { font-family: 'Segoe UI', Arial, sans-serif; font-size: 14px; color: #333; }
            h1 { color: #2c3e50; font-size: 22px; border-bottom: 2px solid #3498db; padding-bottom: 5px; }
            h2 { color: #2980b9; font-size: 18px; margin-top: 20px; }
            code { background-color: #f0f0f0; padding: 2px 4px; border-radius: 3px; font-family: Consolas, monospace; }
            .box { background-color: #e8f4f8; border-left: 4px solid #3498db; padding: 10px; margin: 10px 0; }
            ul { margin-top: 5px; margin-bottom: 5px; }
            li { margin-bottom: 3px; }
        </style>
        </head>
        <body>
            <h1>Справка DesktopPet_v0.1</h1>

            <div class="box">
                <b>Важно:</b> Запускать питомца нужно <b>от имени администратора</b>, 
                иначе он не сможет реагировать на окна других программ и микрофон может не работать.
            </div>

            <h2>Управление</h2>
            <ul>
                <li><b>ЛКМ по питомцу</b> — перетаскивание.</li>
                <li><b>Колёсико мыши по питомцу</b> — активация микрофона («Слушаю...»).</li>
                <li><b>ПКМ по питомцу</b> — контекстное меню (выход).</li>
                <li><b>Иконка в трее</b> — показать/скрыть, настройки, выход.</li>
            </ul>

            <h2>Голосовые команды</h2>
            <p>По умолчанию микрофон активируется по нажатию <code>Ctrl + Alt + F</code> 
            (даже если окно питомца не в фокусе). Изменить это можно во вкладке <b>«Ввод и вывод»</b>.</p>
            <p>Примеры команд:</p>
            <ul>
                <li><i>«Привет»</i>, <i>«Как дела»</i> — общение.</li>
                <li><i>«Который час»</i> — текущее время.</li>
                <li><i>«Громче»</i> / <i>«Тише»</i> — управление звуком Windows.</li>
                <li><i>«Найди котиков»</i> — поиск в интернете.</li>
                <li><i>«Открой стим»</i> — запуск приложений.</li>
                <li><i>«Пока»</i> — выключение питомца.</li>
            </ul>

            <h2>Как добавить свою команду?</h2>
            <p>Откройте файл <code>assets/commands.toml</code> (кнопка есть на вкладке «Дополнительно»).</p>
            <p>Добавьте блок по шаблону:</p>
            <pre>
[commands.notepad]
triggers = ["открой блокнот", "включи блокнот"]
action = "launch"
target = "C:\\Windows\\System32\\notepad.exe"
replies = ["Открываю блокнот", "Пишем?"]
            </pre>

            <h2>Где лежат настройки и логи?</h2>
            <p>Все данные пользователя хранятся в папке: <br>
            <code>%APPDATA%\\DesktopPet_v0.1\\</code></p>
            <p>Кнопки быстрого доступа к папке и логам есть на вкладке <b>«Дополнительно»</b>.</p>

            <br><br>
            <p align="center" style="color: #888;">© Tenrai Production</p>
        </body>
        </html>
"""
