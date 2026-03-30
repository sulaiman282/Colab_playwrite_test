# Colab DentalCare Account Manager
Colab-optimized headless version of DentalCare Account Manager

## Features
- Headless Chrome by default
- API-based registration
- Keep browser open
- Debug logging disabled
- Optimized for Google Colab environment

## Usage
1. Open `run_colab.ipynb` in Google Colab
2. Fill in the parameters:
   - `GITHUB_REPO_URL`: Your GitHub repository URL
   - `PARALLEL_COUNT`: Number of parallel browsers (recommended: 3-5)
   - `BATCH_COUNT`: Number of accounts to process
   - `DELAY`: Delay between batches (seconds)
   - `MFA_PHONE_URL`: Your phone API service URL
3. Run all cells

## Colab Setup
The notebook will automatically:
- Install required dependencies
- Clone the repository
- Set up Playwright
- Start the account manager

## Resource Limits
| Plan | Max Browsers | Est. Accounts/12hr |
|------|-------------|-------------------|
| Free | 3-5 | 2,000-4,000 |
| Pro | 10-15 | 5,000-8,000 |

## Notes
- Use T4 GPU for better stability (but GPU doesn't speed up browser tasks)
- Save results periodically to avoid data loss on disconnection
- Keep parallel count low (3-5) on free tier to avoid OOM kills
# Colab_playwrite_test
