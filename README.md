endpoints:
  - path: /books
    method: GET
    request_schema:
      type: object
      properties: {}
    response:
      books:
        - id: 1
          title: "To Kill a Mockingbird"
          author: "Harper Lee"
          year: 1960
        - id: 2
          title: "1984"
          author: "George Orwell"
          year: 1949

  - path: /books
    method: POST
    request_schema:
      type: object
      properties:
        title: 
          type: string
        author: 
          type: string
        year: 
          type: integer
      required:
        - title
        - author
        - year
    response:
      message: "Book added successfully"
      book:
        id: 3
        title: "New Book Title"
        author: "New Book Author"
        year: 2024

  - path: /books/{book_id}
    method: GET
    request_schema:
      type: object
      properties:
        book_id: 
          type: string
    response:
      id: 1
      title: "To Kill a Mockingbird"
      author: "Harper Lee"
      year: 1960
