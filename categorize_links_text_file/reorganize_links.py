def reorganize_links(filepath):
    # Read the file
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    # Find header positions
    twitter_idx = -1
    unsorted_idx = -1
    for i, line in enumerate(lines):
        if line.strip().lower() == "twitter":
            twitter_idx = i
        elif line.strip().lower() == "unsorted":
            unsorted_idx = i
    
    if twitter_idx == -1 or unsorted_idx == -1:
        raise ValueError("Could not find required headers")
    
    # Collect twitter links and non-twitter links
    twitter_links = []
    other_links = []
    current_line = unsorted_idx + 1
    
    while current_line < len(lines):
        line = lines[current_line]
        if line.strip() and ("twitter.com" in line.lower() or "x.com" in line.lower()):
            twitter_links.append(line)
        else:
            other_links.append(line)
        current_line += 1
    
    # Reconstruct the file
    new_content = (
        lines[:twitter_idx + 1] +  # Everything up to twitter header
        ['\n'] + twitter_links +   # Twitter links
        lines[twitter_idx + 1:unsorted_idx + 1] +  # Content between headers
        ['\n'] + other_links       # Remaining links
    )
    
    # Write back to file
    with open(filepath, 'w') as f:
        f.writelines(new_content)

# Usage
reorganize_links('./unsorted_links.txt')