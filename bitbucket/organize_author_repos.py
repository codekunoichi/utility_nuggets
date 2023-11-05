'''
The output of counter.py is used to organize and understand
- Who committed the most amount of code
- Which repository is most active with commit
'''
from collections import defaultdict

def read_input_from_file(filename):
    with open(filename, 'r') as file:
        data = file.readlines()
    return data[0], data[1]

def organize_commits():
    # Read input from local file
    total_authors_str, total_repoCommits_str = read_input_from_file("/workspaces/utility_nuggets/bitbucket/count_stats.txt")

    # Extracting dictionaries from the input strings
    total_authors = eval(total_authors_str.split(":", 1)[1].strip())
    total_repoCommits = eval(total_repoCommits_str.split(":", 1)[1].strip())

    # Aggregating author commit counts in case of multiple entries with the same email
    aggregated_authors = defaultdict(int)
    for author, count in total_authors.items():
        aggregated_authors[author] += count

    # Sorting authors and repos in descending order
    sorted_authors = dict(sorted(aggregated_authors.items(), key=lambda item: item[1], reverse=True))
    sorted_repoCommits = dict(sorted(total_repoCommits.items(), key=lambda item: item[1], reverse=True))

    # Output
    print("Authors commit descending:")
    print(sorted_authors)
    print("\nTotal repoCommits descending:")
    print(sorted_repoCommits)

if __name__ == "__main__":
    organize_commits()
