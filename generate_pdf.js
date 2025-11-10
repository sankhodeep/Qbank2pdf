const puppeteer = require('puppeteer');
const path = require('path');
const fs = require('fs');

async function generatePdf() {
    // --- Get command line arguments ---
    const args = process.argv.slice(2);
    if (args.length !== 2) {
        console.error('Usage: node generate_pdf.js <input_html_path> <output_pdf_path>');
        process.exit(1);
    }
    const htmlFilePath = path.resolve(args[0]);
    const outputPdfPath = path.resolve(args[1]);

    if (!fs.existsSync(htmlFilePath)) {
        console.error(`Error: Input HTML file not found at ${htmlFilePath}`);
        process.exit(1);
    }

    try {
        console.log('Launching Puppeteer...');
        const browser = await puppeteer.launch({
            headless: "new",
            args: ['--no-sandbox', '--disable-setuid-sandbox'] // Added for compatibility with some environments
        });
        const page = await browser.newPage();

        console.log(`Reading HTML content from: ${htmlFilePath}`);
        const htmlContent = fs.readFileSync(htmlFilePath, 'utf8');

        // Set the page content and wait for all resources to load
        await page.setContent(htmlContent, {
            waitUntil: 'networkidle0'
        });

        console.log(`Generating PDF and saving to: ${outputPdfPath}`);
        await page.pdf({
            path: outputPdfPath,
            format: 'A4',
            printBackground: true,
            margin: {
                top: '1cm',
                right: '1cm',
                bottom: '1cm',
                left: '1cm'
            }
        });

        await browser.close();
        console.log('PDF generated successfully by Puppeteer.');

    } catch (err) {
        console.error('Error generating PDF with Puppeteer:', err);
        process.exit(1); // Exit with an error code
    }
}

generatePdf();
