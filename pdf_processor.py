import json
import os
import subprocess
import tempfile
import threading
import sys
import markdown
import base64
import mimetypes
from PySide6.QtCore import QObject, Signal

class WorkerSignals(QObject):
    """
    Defines the signals available from a running worker thread.
    Supported signals are:
    - finished: Emits a string message on completion or error.
    - progress: Emits a string message for progress updates.
    """
    finished = Signal(str)
    progress = Signal(str)

class PdfWorker(QObject):
    """
    Worker thread for processing JSON files, generating HTML, and creating a PDF.
    This class is designed to run in a separate thread to keep the UI responsive.
    """
    def __init__(self, folders, output_pdf_path):
        super().__init__()
        self.signals = WorkerSignals()
        self.folders = folders
        self.output_pdf_path = output_pdf_path
        self.is_running = True

    def run(self):
        """The main worker logic that orchestrates the PDF generation."""
        try:
            self.signals.progress.emit("Starting PDF generation process...")

            all_questions = self._parse_questions()
            if not all_questions:
                self.signals.finished.emit("Error: No questions found in the selected folders.")
                return

            self.signals.progress.emit("Generating HTML content...")
            html_content = self._generate_html(all_questions)

            # Write the generated HTML to a temporary file for Puppeteer to access
            with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8', suffix='.html') as temp_html:
                temp_html_path = temp_html.name
                temp_html.write(html_content)

            self.signals.progress.emit("Generated temporary HTML file.")

            # --- Execute the Node.js script to generate the PDF ---
            self.signals.progress.emit("Calling Puppeteer to generate the PDF...")
            node_script_path = os.path.join(os.path.dirname(__file__), 'generate_pdf.js')

            if not os.path.exists(node_script_path):
                raise FileNotFoundError("The 'generate_pdf.js' script was not found.")

            # Use subprocess to run the Node.js script with arguments
            process = subprocess.Popen(
                ['node', node_script_path, temp_html_path, self.output_pdf_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            stdout, stderr = process.communicate()

            if process.returncode != 0:
                raise RuntimeError(f"Puppeteer script failed: {stderr}")

            self.signals.progress.emit("PDF generation complete.")
            self.signals.finished.emit(f"Success! PDF saved to {self.output_pdf_path}")

        except Exception as e:
            self.signals.finished.emit(f"Error: {e}")
        finally:
            # Ensure the temporary HTML file is cleaned up
            if 'temp_html_path' in locals() and os.path.exists(temp_html_path):
                os.remove(temp_html_path)

    def _parse_questions(self):
        """
        Parses 'questions.json' from all selected folders and aggregates the questions.
        """
        questions = []
        for folder_path in self.folders:
            json_path = os.path.join(folder_path, 'questions.json')
            self.signals.progress.emit(f"Reading {json_path}...")
            if os.path.exists(json_path):
                with open(json_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    # Add the base folder path to each question object.
                    # This is crucial for resolving relative media paths later.
                    for q in data:
                        q['base_path'] = folder_path
                    questions.extend(data)
            else:
                self.signals.progress.emit(f"Warning: questions.json not found in {folder_path}")
        return questions

    def _generate_html(self, questions):
        """
        Generates a single HTML string containing all questions and necessary styling.
        """
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Question Bank</title>
            <link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;700&display=swap" rel="stylesheet">
            <style>
                {self._get_css_styles()}
            </style>
        </head>
        <body>
        """

        current_folder = None
        # Append each question formatted as an HTML block
        for question in questions:
            folder = question.get('base_path')
            if folder != current_folder:
                folder_name = os.path.basename(folder)
                # Transform output_X to Module X
                if folder_name.startswith('output_'):
                    display_name = folder_name.replace('output_', 'Module ')
                else:
                    display_name = folder_name.replace('_', ' ').title()
                
                html += f"""
                <div class="module-header-page">
                    <h1>{display_name}</h1>
                </div>
                <div class="page-break"></div>
                """
                current_folder = folder
            html += self._format_question_as_html(question)

        html += "</body></html>"
        return html

    def _format_question_as_html(self, question):
        """
        Converts a single question JSON object into its HTML representation.
        """
        q_html = f"<h1>Question {question.get('question_number', '')}</h1>"
        # Convert markdown text to HTML
        question_text_html = markdown.markdown(question.get('text', ''), extensions=['tables'])
        q_html += f"<div class='question-text'>{question_text_html}</div>"

        # --- Handle Question Image ---
        if question.get('question_media_path'):
            # Normalize path separators for cross-platform compatibility
            media_path = question['question_media_path'].replace('\\', '/')
            img_path = os.path.join(question['base_path'], media_path)
            if os.path.exists(img_path):
                # Convert image to base64 and embed it directly in the HTML
                img_uri = self._image_to_base64_uri(img_path)
                q_html += f'<img src="{img_uri}" alt="Question Image" style="max-width: 100%; height: auto;"/>'

        # --- Handle Options ---
        q_html += "<div>"
        correct_answer_text = "N/A"
        for option in question.get('options', []):
            if option.get('is_correct_answer', False):
                correct_answer_text = option.get('text', '')
            # Display the option text. The correct one will be bolded later.
            q_html += f"<p>{option.get('text', '')}</p>"
        q_html += "</div>"

        # --- Display Correct Answer in Bold ---
        q_html += f"<p><b>Correct Answer: {correct_answer_text}</b></p>"

        # --- Handle Labels (Question Tags) ---
        if question.get('labels'):
            labels_html = " ".join([f"<span class='label'>{label}</span>" for label in question.get('labels', [])])
            q_html += f"<div class='labels-container'>{labels_html}</div>"

        # --- Handle Explanation Elements ---
        q_html += "<h2>Explanation</h2>"
        for element in question.get('explanation_elements', []):
            if element.get('type') == 'text':
                q_html += f"<p>{element.get('content', '')}</p>"
            elif element.get('type') == 'image':
                media_path = element.get('path', '').replace('\\', '/')
                img_path = os.path.join(question['base_path'], media_path)
                if os.path.exists(img_path):
                    img_uri = self._image_to_base64_uri(img_path)
                    q_html += f'<img src="{img_uri}" alt="Explanation Image" style="max-width: 100%; height: auto;"/>'
            elif element.get('type') == 'table_processed_vlm':
                # Convert the JSON table data into an HTML table
                table_data = element.get('data', {}).get('table', [])
                if table_data:
                    headers = table_data[0].keys()
                    q_html += "<table><thead><tr>"
                    for header in headers:
                        q_html += f"<th>{header}</th>"
                    q_html += "</tr></thead><tbody>"
                    for row in table_data:
                        q_html += "<tr>"
                        for header in headers:
                            q_html += f"<td>{row.get(header, '')}</td>"
                        q_html += "</tr>"
                    q_html += "</tbody></table>"

        q_html += "<div class='page-break'></div>" # Adds a page break after each question
        return q_html

    def _get_css_styles(self):
        """Returns the CSS string to be embedded in the HTML."""
        return """
        @page { margin: 1cm; }
        .page-break { page-break-after: always; }
        body { font-family: 'Roboto', 'Noto Color Emoji', sans-serif; font-size: 13pt; font-weight: 400; line-height: 1.5; color: #1a1a1a; margin: 0; }
        h1 { font-size: 12pt; font-weight: bold; color: #000; margin-top: 1.5em; margin-bottom: 8px; padding-bottom: 4px; border-bottom: 1px solid #eaeaea; }
        h1:first-child { margin-top: 0; }
        h2 { font-size: 11pt; font-weight: bold; color: #333; margin-top: 1em; margin-bottom: 0.5em; }
        p { margin-top: 0; margin-bottom: 1em; }
        pre { background-color: #f4f4f4; border: 1px solid #ddd; border-radius: 4px; padding: 1em; white-space: pre-wrap; word-wrap: break-word; }
        code { font-family: 'Courier New', Courier, monospace; font-size: 12pt; }
        table { width: 100%; border-collapse: collapse; margin-bottom: 1em; font-size: 11pt; background: #fff; box-shadow: 0 2px 8px rgba(0,0,0,0.03); }
        table th { background: #f7f7f7; color: #333; font-weight: bold; padding: 10px 8px; border: 1px solid #e0e0e0; text-align: left; }
        table td { padding: 10px 8px; border: 1px solid #e0e0e0; color: #222; }
        table tr:nth-child(even) { background: #fafafa; }
        table tr:hover { background: #f0f4ff; }
        .labels-container { margin-top: 10px; margin-bottom: 10px; }
        .label { background-color: #e7e7e7; color: #333; padding: 3px 8px; border-radius: 12px; font-size: 9pt; margin-right: 5px; }
        .module-header-page { text-align: center; padding-top: 40%; }
        .module-header-page h1 { font-size: 40pt; border: none; color: #333; }
        """
        
    def _image_to_base64_uri(self, image_path):
        """Converts a local image file to a base64 data URI."""
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = 'application/octet-stream'  # Default MIME type

        with open(image_path, "rb") as image_file:
            encoded_string = base64.b64encode(image_file.read()).decode()
        
        return f"data:{mime_type};base64,{encoded_string}"

    def stop(self):
        """Stops the worker thread."""
        self.is_running = False
