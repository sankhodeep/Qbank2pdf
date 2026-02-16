import sys
import os
import re
import threading
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QMessageBox, QLineEdit,
    QDialog, QListWidget, QListWidgetItem, QDialogButtonBox,
    QComboBox, QInputDialog
)
from PySide6.QtCore import Qt
from pdf_processor import PdfWorker, BatchPdfWorker

def natural_sort_key(s):
    """
    A key function for natural sorting.
    Splits the string into a list of strings and numbers.
    """
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'([0-9]+)', s)]

# --- Folder Selection Dialog ---
class FolderSelectionDialog(QDialog):
    """
    A dialog window that allows the user to select and reorder folders.
    """
    def __init__(self, folders, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select and Order Folders")
        self.setGeometry(200, 200, 500, 600)
        layout = QVBoxLayout(self)

        # --- Folder Selection Input ---
        selection_layout = QHBoxLayout()
        self.folder_input = QLineEdit()
        self.folder_input.setPlaceholderText("e.g., 1, 3, 5-10")
        selection_layout.addWidget(self.folder_input)
        
        apply_button = QPushButton("Apply Selection")
        apply_button.clicked.connect(self.apply_folder_selection)
        selection_layout.addWidget(apply_button)
        layout.addLayout(selection_layout)
        
        self.list_widget = QListWidget()
        self.list_widget.setDragDropMode(QListWidget.InternalMove)

        for folder in folders:
            item = QListWidgetItem(folder)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)  # Default to unchecked
            self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)

        button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def apply_folder_selection(self):
        """
        Applies the selection from the input string to the list widget.
        """
        try:
            # --- Parse the input string ---
            input_text = self.folder_input.text()
            selected_numbers = set()
            parts = [p.strip() for p in input_text.split(',') if p.strip()]
            for part in parts:
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    selected_numbers.update(range(start, end + 1))
                else:
                    selected_numbers.add(int(part))
            
            # --- Apply to the list widget ---
            for i in range(self.list_widget.count()):
                item = self.list_widget.item(i)
                folder_name = item.text()
                # Extract leading number from folder name
                # Look for the pattern 'output_[number]' to get the module number
                match = re.search(r'output_(\d+)', folder_name)
                if match:
                    folder_num = int(match.group(1))
                    if folder_num in selected_numbers:
                        item.setCheckState(Qt.Checked)
                    else:
                        item.setCheckState(Qt.Unchecked)



        except ValueError:
            QMessageBox.warning(self, "Invalid Input", "Please use numbers and ranges (e.g., 1, 5-10).")
            
    def get_selected_folders_in_order(self):
        """
        Retrieves the list of checked folders in their current order.
        """
        selected_folders = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if item.checkState() == Qt.Checked:
                selected_folders.append(item.text())
        return selected_folders

# --- Main Application Window ---
class MainWindow(QMainWindow):
    """
    The main application window for the QBank PDF Generator.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QBank PDF Generator")
        self.setGeometry(100, 100, 700, 350)

        # --- Config Data ---
        self.config_file = "configs.json"
        self.configs = {}

        # --- Member variables ---
        self.root_folder_path = ""
        self.output_folder_path = ""
        self.selected_folders = []

        # --- Central Widget and Layout ---
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # --- Config Management UI ---
        config_layout = QHBoxLayout()
        config_layout.addWidget(QLabel("Config:"))
        self.config_combo = QComboBox()
        self.config_combo.setPlaceholderText("Select a config...")
        self.config_combo.activated.connect(self.load_configuration)
        config_layout.addWidget(self.config_combo)

        save_config_btn = QPushButton("Save Config")
        save_config_btn.clicked.connect(self.save_configuration)
        config_layout.addWidget(save_config_btn)

        delete_config_btn = QPushButton("Delete Config")
        delete_config_btn.clicked.connect(self.delete_configuration)
        config_layout.addWidget(delete_config_btn)
        main_layout.addLayout(config_layout)

        # --- Root Folder Selection UI ---
        root_folder_layout = QHBoxLayout()
        root_folder_layout.addWidget(QLabel("Root Folder:"))
        self.root_folder_label = QLineEdit("No folder selected...")
        self.root_folder_label.setReadOnly(True)
        root_folder_layout.addWidget(self.root_folder_label)
        
        choose_root_folder_button = QPushButton("Browse...")
        choose_root_folder_button.clicked.connect(self.select_root_folder)
        root_folder_layout.addWidget(choose_root_folder_button)

        select_modules_button = QPushButton("Select Modules...")
        select_modules_button.clicked.connect(self.open_module_selection)
        root_folder_layout.addWidget(select_modules_button)
        main_layout.addLayout(root_folder_layout)

        # --- Output Folder Selection UI ---
        output_folder_layout = QHBoxLayout()
        output_folder_layout.addWidget(QLabel("Output Folder:"))
        self.output_folder_label = QLineEdit("No folder selected...")
        self.output_folder_label.setReadOnly(True)
        output_folder_layout.addWidget(self.output_folder_label)
        
        choose_output_button = QPushButton("Browse...")
        choose_output_button.clicked.connect(self.select_output_folder)
        output_folder_layout.addWidget(choose_output_button)
        main_layout.addLayout(output_folder_layout)

        # --- Selected Folders Info Label ---
        self.selected_folders_label = QLabel("Selected folders: 0")
        main_layout.addWidget(self.selected_folders_label)

        # --- Bottom Bar with Start Button and Status Label ---
        bottom_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Generation")
        self.start_button.clicked.connect(self.start_processing)
        bottom_layout.addWidget(self.start_button)

        self.batch_button = QPushButton("Batch Generate All")
        self.batch_button.clicked.connect(self.start_batch_processing)
        bottom_layout.addWidget(self.batch_button)

        self.status_label = QLabel("Status: Ready")
        bottom_layout.addWidget(self.status_label, 1) # Give it more space
        main_layout.addLayout(bottom_layout)

        # --- Initialize Configs ---
        self.load_all_configs()
        self.populate_config_combo()
        self.validate_inputs() # Set initial state of the start button

    # --- Config Methods ---
    def load_all_configs(self):
        """Loads all configurations from the JSON file."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.configs = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.configs = {}

    def save_all_configs(self):
        """Saves all configurations to the JSON file."""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.configs, f, indent=4)
        except IOError as e:
            QMessageBox.critical(self, "Error", f"Could not save configs to file: {e}")

    def populate_config_combo(self):
        """Populates the config dropdown menu."""
        self.config_combo.clear()
        self.config_combo.addItem("Select a config...")
        self.config_combo.addItems(sorted(self.configs.keys()))

    def save_configuration(self):
        """Prompts for a name and saves the current paths as a configuration."""
        config_name, ok = QInputDialog.getText(self, "Save Configuration", "Enter a name for this configuration:")
        if ok and config_name:
            self.configs[config_name] = {
                "root_path": self.root_folder_path,
                "output_folder": self.output_folder_path
            }
            self.save_all_configs()
            self.populate_config_combo()
            self.config_combo.setCurrentText(config_name)
            QMessageBox.information(self, "Success", f"Configuration '{config_name}' saved.")

    def load_configuration(self):
        """Loads the paths from the selected configuration."""
        config_name = self.config_combo.currentText()
        if config_name and config_name != "Select a config...":
            config_data = self.configs.get(config_name)
            if config_data:
                self.root_folder_path = config_data.get("root_path", "")
                self.root_folder_label.setText(self.root_folder_path if self.root_folder_path else "No folder selected...")
                
                self.output_folder_path = config_data.get("output_folder", "")
                self.output_folder_label.setText(self.output_folder_path if self.output_folder_path else "No folder selected...")
                
                # Reset selected folders when changing config
                self.selected_folders = []
                self.selected_folders_label.setText("Selected folders: 0")
                self.validate_inputs()

    def delete_configuration(self):
        """Deletes the currently selected configuration."""
        config_name = self.config_combo.currentText()
        if config_name and config_name != "Select a config...":
            reply = QMessageBox.question(self, "Delete Configuration",
                                       f"Are you sure you want to delete '{config_name}'?",
                                       QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                if config_name in self.configs:
                    del self.configs[config_name]
                    self.save_all_configs()
                    self.populate_config_combo()
                    QMessageBox.information(self, "Success", f"Configuration '{config_name}' deleted.")

    def select_root_folder(self):
        """
        Opens a dialog to select the root folder.
        """
        folder_path = QFileDialog.getExistingDirectory(self, "Select the Root Folder", self.root_folder_path)
        if not folder_path:
            return

        self.root_folder_path = folder_path
        self.root_folder_label.setText(folder_path)
        
        # Reset selected folders when root changes
        self.selected_folders = []
        self.selected_folders_label.setText("Selected folders: 0")
        self.validate_inputs()

    def open_module_selection(self):
        """
        Opens the folder selection and ordering dialog for sub-folders.
        """
        if not self.root_folder_path or not os.path.exists(self.root_folder_path):
            QMessageBox.warning(self, "No Root Folder", "Please select a valid root folder first.")
            return

        try:
            # Find all subdirectories in the selected root folder
            subfolders = [d for d in os.listdir(self.root_folder_path) if os.path.isdir(os.path.join(self.root_folder_path, d))]
            subfolders.sort(key=natural_sort_key) # Use natural sorting

            if not subfolders:
                QMessageBox.information(self, "No Folders", "No sub-folders found in the selected directory.")
                self.selected_folders = []
                self.validate_inputs()
                return

            # Show the folder selection and ordering dialog
            dialog = FolderSelectionDialog(subfolders, self)
            if dialog.exec():
                # Get the full paths of the selected folders
                self.selected_folders = [os.path.join(self.root_folder_path, f) for f in dialog.get_selected_folders_in_order()]
                self.selected_folders_label.setText(f"Selected folders: {len(self.selected_folders)}")
            else:
                # Keep existing selection if cancelled?
                # Actually, the original code reset it to empty if cancelled.
                # Let's keep it as is for consistency, but maybe it's better to keep old selection.
                # The original code: self.selected_folders = [] # User cancelled
                pass
                
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not read sub-folders: {e}")
            self.selected_folders = []

        self.validate_inputs()

    def select_output_folder(self):
        """
        Opens a dialog to specify the default output folder.
        """
        folder_path = QFileDialog.getExistingDirectory(self, "Select Output Folder", self.output_folder_path)
        if folder_path:
            self.output_folder_path = folder_path
            self.output_folder_label.setText(folder_path)
        self.validate_inputs()

    def validate_inputs(self):
        """
        Enable or disable the buttons based on whether all necessary
        inputs have been provided.
        """
        is_valid = (
            bool(self.selected_folders) and
            os.path.isdir(self.output_folder_path)
        )
        self.start_button.setEnabled(is_valid)

        # Batch button only needs root folder and output folder
        is_batch_valid = (
            bool(self.root_folder_path) and 
            os.path.isdir(self.root_folder_path) and
            os.path.isdir(self.output_folder_path)
        )
        self.batch_button.setEnabled(is_batch_valid)

    def start_batch_processing(self):
        """
        Automatically finds all modules and generates separate PDFs for each.
        """
        if not self.root_folder_path or not os.path.isdir(self.root_folder_path):
            QMessageBox.warning(self, "Invalid Root", "Please select a valid root folder.")
            return

        try:
            subfolders = [d for d in os.listdir(self.root_folder_path) if os.path.isdir(os.path.join(self.root_folder_path, d))]
            subfolders.sort(key=natural_sort_key)

            if not subfolders:
                QMessageBox.information(self, "No Folders", "No sub-folders found in the root directory.")
                return

            tasks = []
            for folder_name in subfolders:
                folder_path = os.path.join(self.root_folder_path, folder_name)
                # Check if questions.json exists
                if not os.path.exists(os.path.join(folder_path, 'questions.json')):
                    continue
                    
                # Determine display name for PDF filename
                if folder_name.startswith('output_'):
                    display_name = folder_name.replace('output_', 'Module ')
                else:
                    display_name = folder_name.replace('_', ' ').title()
                
                output_pdf_path = os.path.join(self.output_folder_path, f"{display_name}.pdf")
                tasks.append(([folder_path], output_pdf_path))

            if not tasks:
                QMessageBox.information(self, "No Valid Modules", "No folders with 'questions.json' were found.")
                return

            reply = QMessageBox.question(self, "Confirm Batch", 
                                        f"Found {len(tasks)} modules. Start batch generation?",
                                        QMessageBox.Yes | QMessageBox.No)
            if reply != QMessageBox.Yes:
                return

            self.start_button.setEnabled(False)
            self.batch_button.setEnabled(False)
            self.status_label.setText("Status: Batch Starting...")

            # --- Setup and run worker thread ---
            self.worker = BatchPdfWorker(tasks)
            self.thread = threading.Thread(target=self.worker.run)
            self.worker.signals.progress.connect(self.update_status)
            self.worker.signals.finished.connect(self.on_processing_finished)
            self.thread.start()

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to start batch: {e}")

    def start_processing(self):
        """
        Kicks off the PDF generation process in a background thread.
        Prompts for a filename first.
        """
        # Prompt for output file name in the selected output folder
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save PDF As", self.output_folder_path, "PDF Files (*.pdf)"
        )
        
        if not filepath:
            return

        self.start_button.setEnabled(False)
        self.batch_button.setEnabled(False)
        self.status_label.setText("Status: Starting...")

        # --- Setup and run worker thread ---
        self.worker = PdfWorker(self.selected_folders, filepath)
        self.thread = threading.Thread(target=self.worker.run)
        self.worker.signals.progress.connect(self.update_status)
        self.worker.signals.finished.connect(self.on_processing_finished)
        self.thread.start()

    def update_status(self, message):
        """
        Updates the status label with progress from the worker thread.
        """
        self.status_label.setText(f"Status: {message}")
        print(message) # Also log to terminal for debugging

    def on_processing_finished(self, message):
        """
        Handles the completion signal from the worker thread.
        """
        if message.startswith("Error") or "Error" in message:
            QMessageBox.critical(self, "Finished with issues", message)
            self.status_label.setText("Status: Finished with errors")
        else:
            QMessageBox.information(self, "Success", message)
            self.status_label.setText("Status: Ready")

        self.validate_inputs() # Re-enable the start button if inputs are still valid

    def closeEvent(self, event):
        """
        Ensure the worker thread is stopped gracefully if running when the
        application is closed.
        """
        if hasattr(self, 'worker') and self.thread.is_alive():
            self.worker.stop()
            self.thread.join()
        event.accept()

def main():
    """The main entry point of the application."""
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
