import requests
from typing import List, Dict, Any
import os
from dotenv import load_dotenv
import json
from datetime import datetime

load_dotenv()


class GithubRepoFetcher:
    def __init__(self):
        self.base_url = "https://api.github.com"
        token = os.getenv('GITHUB_TOKEN')
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable is required")
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {token}"
        }

    def fetch_python_repos(self, min_stars: int = 100, per_page: int = 5) -> List[Dict]:
        query_params = {
            "q": "language:python",  # Python as primary language
            "sort": "stars",
            "order": "desc",
            "per_page": per_page
        }

        try:
            response = requests.get(
                f"{self.base_url}/search/repositories",
                headers=self.headers,
                params=query_params
            )
            response.raise_for_status()

            repos = response.json()["items"]
            # Filter for repos where Python is the most used language
            return [
                {
                    "name": repo["full_name"],
                    "stars": repo["stargazers_count"],
                    "description": repo["description"],
                    "url": repo["html_url"],
                    "created_at": repo["created_at"]
                }
                for repo in repos
                if repo["language"] == "Python"
            ]

        except requests.exceptions.RequestException as e:
            print(f"Error fetching repositories: {e}")
            return []

    def get_commit_details(self, repo_name: str, commit_sha: str) -> Dict:
        url = f"{self.base_url}/repos/{repo_name}/commits/{commit_sha}"
        response = requests.get(url, headers=self.headers)
        return response.json()

    def _matches_keywords(self, text: str, keywords: List[str]) -> bool:
        text = text.lower()
        return any(keyword.lower() in text for keyword in keywords)

    def get_filtered_commits(
        self,
        repo_name: str,
        max_commits: int = 100,  # Increase default to find more commits
        include_keywords: List[str] = None,
        exclude_keywords: List[str] = None
    ) -> List[Dict]:
        commits_url = f"{self.base_url}/repos/{repo_name}/commits"
        params = {"per_page": 30}  # GitHub API page size
        include_keywords = include_keywords or []
        exclude_keywords = exclude_keywords or []

        try:
            commits = []
            page = 1
            total_requested = 0

            # Implement pagination to get more commits
            while total_requested < max_commits:
                params["page"] = page
                response = requests.get(
                    commits_url, headers=self.headers, params=params)
                response.raise_for_status()

                page_commits = response.json()
                if not page_commits:
                    break  # No more commits

                print(f"Processing page {page} ({len(page_commits)} commits)")

                for commit in page_commits:
                    message = commit["commit"]["message"]

                    # Apply keyword filters
                    if self._matches_keywords(message, exclude_keywords):
                        continue
                    if include_keywords and not self._matches_keywords(message, include_keywords):
                        continue

                    details = self.get_commit_details(repo_name, commit["sha"])

                    # Filter for Python files with small changes and non-empty patches
                    python_changes = [
                        file for file in details.get("files", [])
                        if file["filename"].endswith(".py")
                        and (file.get("additions", 0) + file.get("deletions", 0)) <= 10
                        # Only include changes with patches
                        and file.get("patch")
                    ]

                    if python_changes:
                        commits.append({
                            "sha": commit["sha"],
                            "message": message,
                            "date": commit["commit"]["author"]["date"],
                            "changes": [
                                {
                                    "file": f["filename"],
                                    "patch": f["patch"]
                                }
                                for f in python_changes
                            ]
                        })

                        # Show progress
                        if len(commits) % 5 == 0:
                            print(
                                f"Found {len(commits)} bug-fix commits so far...")

                    if len(commits) >= max_commits:
                        break

                page += 1
                total_requested += len(page_commits)

                # Avoid rate limiting
                if page > 1:
                    print("Waiting to avoid rate limiting...")
                    time.sleep(1)

            if not commits:
                print(f"No commits matching criteria found in {repo_name}")
            else:
                print(f"Found {len(commits)} matching commits for {repo_name}")

            return commits

        except requests.exceptions.RequestException as e:
            print(f"Error fetching commits: {e}")
            return []


def save_commits_data(repo_name: str, commits_data: List[Dict[str, Any]],
                      base_dir: str = "commits_data"):
    """Save commits data to a JSON file organized by repository"""
    os.makedirs(base_dir, exist_ok=True)
    repo_filename = repo_name.replace('/', '_')
    filepath = os.path.join(base_dir, f"{repo_filename}_commits.json")

    # Simplify the data structure to focus on bug-related information
    simplified_commits = {
        "repo_name": repo_name,
        "commits": [
            {
                "sha": commit["sha"],
                "message": commit["message"],
                "changes": [
                    {
                        "file": change["file"],
                        "patch": change["patch"]
                    }
                    for change in commit["changes"]
                ]
            }
            for commit in commits_data
        ]
    }

    with open(filepath, 'w') as f:
        json.dump(simplified_commits, f, indent=2)

    print(f"Commit data for {repo_name} saved to {filepath}")


if __name__ == "__main__":
    import time
    fetcher = GithubRepoFetcher()

    # Get repos with more stars to increase chances of finding bug fixes
    print("Fetching repositories...")
    python_repos = fetcher.fetch_python_repos(min_stars=500, per_page=20)

    if not python_repos:
        print("No repositories found. Check your GitHub token and rate limits.")
        exit(1)

    print(f"Found {len(python_repos)} repositories")

    # Configure commit filtering with broader keywords
    include_keywords = [
        "fix", "bug", "error", "issue", "crash", "exception",
        "wrong", "fail", "problem", "incorrect", "invalid",
        "broken", "repair", "resolve"
    ]
    exclude_keywords = ["merge", "sync", "typo",
                        "docs", "documentation", "readme"]

    # Process each repository
    successful_repos = 0
    for idx, repo in enumerate(python_repos):
        repo_name = repo["name"]
        print(
            f"\nProcessing repository {idx+1}/{len(python_repos)}: {repo_name}")

        try:
            # Get commits with bugs/fixes (more commits per repo)
            commits = fetcher.get_filtered_commits(
                repo_name,
                max_commits=50,
                include_keywords=include_keywords,
                exclude_keywords=exclude_keywords
            )

            if not commits:
                print(
                    f"No matching commits found for {repo_name}, skipping...")
                continue

            # Simplified commit enrichment - remove temporal data
            enriched_commits = [
                {
                    "sha": commit["sha"],
                    "message": commit["message"],
                    "changes": commit["changes"]
                }
                for commit in commits
            ]

            if enriched_commits:
                save_commits_data(repo_name, enriched_commits)
                successful_repos += 1

        except Exception as e:
            print(f"Error processing repository {repo_name}: {e}")

        # Avoid rate limiting between repositories
        if idx < len(python_repos) - 1:
            print("Waiting between repositories to avoid rate limiting...")
            time.sleep(2)

    print(
        f"\nSuccessfully processed {successful_repos} out of {len(python_repos)} repositories")
