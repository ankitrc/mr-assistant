"""Fictional name pools by region (any match with a real person is coincidental)."""

TAMIL = {
    "male": ["Senthil", "Karthik", "Arun", "Prakash", "Rajesh", "Suresh", "Ramesh", "Vignesh", "Balaji", "Ganesh",
             "Murali", "Saravanan", "Dinesh", "Ashok", "Hari", "Mohan", "Kannan", "Sundar", "Venkat", "Raghavan",
             "Elango", "Kumaresan", "Selvam", "Bharath", "Shankar", "Manikandan", "Prabhu", "Srinivasan", "Anand", "Vijay"],
    "female": ["Lakshmi", "Priya", "Divya", "Kavitha", "Meena", "Revathi", "Anitha", "Deepa", "Sangeetha", "Vidya",
               "Gayathri", "Nithya", "Shalini", "Uma", "Radha", "Janani", "Keerthana", "Malathi", "Sudha", "Padma"],
    "surname": ["R", "S", "K", "M", "N", "P", "V", "T", "G", "A", "B", "J", "Iyer", "Pillai", "Subramanian", "Natarajan"],
}
BENGALI = {
    "male": ["Arijit", "Subhash", "Partha", "Sourav", "Debasish", "Amitava", "Indranil", "Sandip", "Tapas", "Abhijit",
             "Kaushik", "Anirban", "Biswajit", "Pranab", "Rajarshi", "Suman", "Tanmoy", "Arnab", "Joydeep", "Sudipto",
             "Niladri", "Prasenjit", "Sayan", "Dipankar", "Shubhankar"],
    "female": ["Sutapa", "Moumita", "Rituparna", "Sharmistha", "Ananya", "Debjani", "Paromita", "Sanchita", "Madhumita",
               "Tanushree", "Ishita", "Sreya", "Nandini", "Payel", "Rupa"],
    "surname": ["Banerjee", "Chatterjee", "Mukherjee", "Ghosh", "Das", "Sen", "Roy", "Bose", "Dutta", "Chakraborty",
                "Bhattacharya", "Sarkar", "Saha", "Mondal", "Paul", "Ganguly", "Majumdar", "Pal"],
}
MARATHI = {
    "male": ["Sachin", "Amol", "Prashant", "Nilesh", "Sameer", "Vinayak", "Abhijeet", "Mahesh", "Rohan", "Sanjay",
             "Shrikant", "Tushar", "Yogesh", "Ajit", "Milind", "Kedar", "Parag", "Hemant", "Swapnil", "Omkar",
             "Ninad", "Aditya", "Chetan", "Girish", "Mandar"],
    "female": ["Sneha", "Pooja", "Ashwini", "Madhuri", "Shruti", "Manasi", "Rupali", "Vaishali", "Prajakta", "Anuja",
               "Gauri", "Sayali", "Ketaki", "Mrunal", "Aparna"],
    "surname": ["Kulkarni", "Joshi", "Deshpande", "Patil", "Pawar", "Jadhav", "Bhosale", "Shinde", "Kale", "Deshmukh",
                "Apte", "Gokhale", "Phadke", "Karve", "Sathe", "Mane", "Gaikwad", "Chavan"],
}
MUMBAI = {
    "male": MARATHI["male"][:15] + ["Rahul", "Nikhil", "Imran", "Farhan", "Kunal", "Jignesh", "Hitesh", "Vivek",
                                   "Aniruddha", "Cyrus", "Neil", "Aakash"],
    "female": MARATHI["female"][:10] + ["Neha", "Kruti", "Zainab", "Fatima", "Rhea", "Anjali", "Nisha", "Hetal"],
    "surname": ["Shah", "Mehta", "Desai", "Patel", "Iyer", "Nair", "Shaikh", "Khan", "D'Souza", "Fernandes", "Gupta",
                "Agarwal", "Kulkarni", "Joshi", "Patil", "Pawar", "Kapadia", "Merchant", "Bhatt", "Rao"],
}
DELHI = {
    "male": ["Rajiv", "Sanjeev", "Amit", "Vikas", "Rohit", "Deepak", "Manish", "Gaurav", "Pankaj", "Naveen",
             "Sumit", "Ashish", "Varun", "Harpreet", "Jaspreet", "Kapil", "Puneet", "Rakesh", "Tarun", "Vipin",
             "Alok", "Anil", "Sunil", "Manoj", "Yash"],
    "female": ["Neha", "Pooja", "Shweta", "Ritu", "Swati", "Anjali", "Sonia", "Preeti", "Nidhi", "Shalini",
               "Kanika", "Simran", "Gurleen", "Megha", "Payal"],
    "surname": ["Sharma", "Verma", "Gupta", "Malhotra", "Kapoor", "Khanna", "Arora", "Singh", "Bhatia", "Chopra",
                "Sethi", "Aggarwal", "Jain", "Bansal", "Mittal", "Srivastava", "Tandon", "Ahuja", "Grover", "Saini"],
}

BY_TERRITORY = {900001: TAMIL, 900002: MARATHI, 900003: BENGALI, 900004: MUMBAI, 900005: DELHI}
