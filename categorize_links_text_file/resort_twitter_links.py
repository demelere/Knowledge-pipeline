def resort_twitter_links(input_file, output_file):
   with open(input_file, 'r') as f:
       lines = f.readlines()
   
   # Find twitter section
   twitter_start = -1
   twitter_end = -1
   for i, line in enumerate(lines):
       if line.strip().lower() == "twitter":
           twitter_start = i
       elif twitter_start != -1 and line.strip() and not ("twitter.com" in line.lower() or "x.com" in line.lower()):
           twitter_end = i
           break
   if twitter_end == -1:
       twitter_end = len(lines)
   
   # Extract usernames and sort
   twitter_links = []
   for line in lines[twitter_start+1:twitter_end]:
       if not line.strip():
           continue
       # Extract username after twitter.com/ or x.com/
       username = line.split('.com/')[1].split('/')[0].lower()
       twitter_links.append((username, line))
   
   twitter_links.sort()  # Sort by username tuple[0]
   
   # Reconstruct file
   new_content = (
       lines[:twitter_start+1] +
       [link[1] for link in twitter_links] +
       lines[twitter_end:]
   )
   
   with open(output_file, 'w') as f:
       f.writelines(new_content)

# Usage
resort_twitter_links('./unsorted_links.txt', 'sorted_links.txt')