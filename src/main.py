import requests
from typing import List, Dict
import os
from dotenv import load_dotenv

load_dotenv()


class GithubRepoFetcher:
    def __init__(self):
        self.base_url = "https://api.github.com"
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN environment variable is required")
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "Authorization": f"token {token}",
        }

    def fetch_python_repos(self, min_stars: int = 100, per_page: int = 5) -> List[Dict]:
        query_params = {
            "q": "language:python",  # Python as primary language
            "sort": "stars",
            "order": "desc",
            "per_page": per_page,
        }

        try:
            response = requests.get(
                f"{self.base_url}/search/repositories",
                headers=self.headers,
                params=query_params,
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
                    "created_at": repo["created_at"],
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
        max_commits: int = 10,
        include_keywords: List[str] = None,
        exclude_keywords: List[str] = None,
    ) -> List[Dict]:
        commits_url = f"{self.base_url}/repos/{repo_name}/commits"
        params = {"per_page": max_commits}
        include_keywords = include_keywords or []
        exclude_keywords = exclude_keywords or []

        try:
            response = requests.get(commits_url, headers=self.headers, params=params)
            response.raise_for_status()
            commits = []

            for commit in response.json():
                message = commit["commit"]["message"]

                # Skip if matches exclude keywords
                if self._matches_keywords(message, exclude_keywords):
                    continue

                # Skip if include keywords specified but doesn't match
                if include_keywords and not self._matches_keywords(
                    message, include_keywords
                ):
                    continue

                details = self.get_commit_details(repo_name, commit["sha"])

                # Filter for Python files with small changes and non-empty patches
                python_changes = [
                    file
                    for file in details.get("files", [])
                    if file["filename"].endswith(".py")
                    and (file.get("additions", 0) + file.get("deletions", 0)) <= 10
                    and file.get("patch")  # Only include changes with patches
                ]

                if python_changes:
                    commits.append(
                        {
                            "sha": commit["sha"],
                            "message": message,
                            "date": commit["commit"]["author"]["date"],
                            "changes": [
                                {
                                    "file": f["filename"],
                                    "additions": f.get("additions", 0),
                                    "deletions": f.get("deletions", 0),
                                    "patch": f["patch"],
                                }
                                for f in python_changes
                            ],
                        }
                    )

            return commits

        except requests.exceptions.RequestException as e:
            print(f"Error fetching commits: {e}")
            return []


if __name__ == "__main__":
    fetcher = GithubRepoFetcher()
    python_repos = fetcher.fetch_python_repos(per_page=5)
    # If you want to use hardcoded repo instead:
    # python_repos = [{"name": "hummingbot/hummingbot"}]

    include_keywords = ["fix", "bugfix"]
    exclude_keywords = ["merge", "sync"]

    for repo in python_repos[:5]:
        print(f"\nRepository: {repo['name']}")
        commits = fetcher.get_filtered_commits(
            repo["name"],
            max_commits=10,
            include_keywords=include_keywords,
            exclude_keywords=exclude_keywords,
        )

        for commit in commits:  # Show first 5 matching commits
            print(f"\nCommit: {commit['sha'][:8]}")
            print(f"Message: {commit['message']}")
            for change in commit["changes"]:
                print(f"File: {change['file']}")
                print("Patch:")
                print(change["patch"])
