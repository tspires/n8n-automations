# n8n-automations

Python code snippets for n8n workflows with automatic deployment.

## Setup

### 1. Generate n8n API Key

1. Open your n8n instance
2. Go to **Settings** > **API**
3. Click **Create API Key**
4. Copy the key

### 2. Configure GitHub Secrets

Add these secrets to your GitHub repo (**Settings** > **Secrets and variables** > **Actions**):

- `N8N_HOST` - Your n8n URL (e.g., `http://your-n8n-host:5678`)
- `N8N_API_KEY` - The API key from step 1

### 3. Mark Your n8n Workflow Nodes

In your n8n Python Code nodes, add a snippet marker as the first line:

```python
# snippet: url_health_check
# ... rest of code will be auto-replaced on deploy
```

## Usage

### Auto-Deploy (GitHub Actions)

Push changes to `snippets/` and they'll automatically deploy to your n8n instance.

### Manual Deploy

```bash
# Set environment
export N8N_HOST=http://localhost:5678
export N8N_API_KEY=your-api-key

# Deploy all snippets
python deploy.py

# Deploy specific snippet
python deploy.py --snippet url_health_check

# Dry run
python deploy.py --dry-run

# List available snippets
python deploy.py --list
```

## Available Snippets

### url_health_check

Quick URL validation to filter out low-quality company prospects.

**Input fields:** `url`, `website`, `company_url`, or `domain`

**Output fields:**
- `url_valid` - boolean
- `url_status_code` - HTTP status code
- `url_error` - error message if failed

## Adding New Snippets

1. Create your Python file in `snippets/`
2. Add `# snippet: your_snippet_id` as the first line
3. Register in `snippets/snippet_registry.json`
4. Push to trigger deploy
