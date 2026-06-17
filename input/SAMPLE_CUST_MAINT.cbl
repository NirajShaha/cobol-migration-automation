       IDENTIFICATION DIVISION.
       PROGRAM-ID. CUST-MAINT.
       AUTHOR. SAMPLE-PROGRAM.
      *
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT CUSTOMER-FILE ASSIGN TO 'CUSTFILE'
               ORGANIZATION IS INDEXED
               ACCESS MODE IS DYNAMIC
               RECORD KEY IS CUST-ID
               FILE STATUS IS WS-FILE-STATUS.
      *
       DATA DIVISION.
       FILE SECTION.
       FD CUSTOMER-FILE.
       01 CUSTOMER-RECORD.
           05 CUST-ID              PIC X(10).
           05 CUST-NAME            PIC X(30).
           05 CUST-ADDRESS         PIC X(50).
           05 CUST-PHONE           PIC X(15).
           05 CUST-EMAIL           PIC X(40).
           05 CUST-STATUS          PIC X(01).
           05 CUST-BALANCE         PIC 9(7)V99.
           05 CUST-CREDIT-LIMIT    PIC 9(7)V99.
           05 CUST-LAST-UPDATE     PIC X(10).
      *
       WORKING-STORAGE SECTION.
       01 WS-FILE-STATUS           PIC X(02).
       01 WS-FUNCTION-CODE         PIC X(01).
           88 WS-ADD               VALUE 'A'.
           88 WS-UPDATE            VALUE 'U'.
           88 WS-DELETE            VALUE 'D'.
           88 WS-INQUIRY           VALUE 'I'.
       01 WS-MSG-FIELD             PIC X(80).
       01 WS-CONFIRM               PIC X(01).
      *
       01 SCR-CUSTOMER-ID          PIC X(10).
       01 SCR-CUSTOMER-NAME        PIC X(30).
       01 SCR-CUSTOMER-ADDRESS     PIC X(50).
       01 SCR-CUSTOMER-PHONE       PIC X(15).
       01 SCR-CUSTOMER-EMAIL       PIC X(40).
       01 SCR-CUSTOMER-STATUS      PIC X(01).
       01 SCR-CUSTOMER-BALANCE     PIC X(10).
       01 SCR-CREDIT-LIMIT         PIC X(10).
      *
       PROCEDURE DIVISION.
       MAIN-PROCESS.
           PERFORM INITIALIZE-SCREEN
           PERFORM PROCESS-REQUEST
               UNTIL WS-FUNCTION-CODE = 'X'
           PERFORM CLEANUP-AND-EXIT
           STOP RUN.
      *
       INITIALIZE-SCREEN.
           MOVE SPACES TO SCR-CUSTOMER-ID
           MOVE SPACES TO SCR-CUSTOMER-NAME
           MOVE SPACES TO SCR-CUSTOMER-ADDRESS
           MOVE SPACES TO SCR-CUSTOMER-PHONE
           MOVE SPACES TO SCR-CUSTOMER-EMAIL
           MOVE SPACES TO SCR-CUSTOMER-STATUS
           MOVE SPACES TO SCR-CUSTOMER-BALANCE
           MOVE SPACES TO SCR-CREDIT-LIMIT
           MOVE SPACES TO WS-MSG-FIELD.
      *
       PROCESS-REQUEST.
           ACCEPT WS-FUNCTION-CODE
           EVALUATE WS-FUNCTION-CODE
               WHEN 'A'
                   PERFORM ADD-CUSTOMER
               WHEN 'U'
                   PERFORM UPDATE-CUSTOMER
               WHEN 'D'
                   PERFORM DELETE-CUSTOMER
               WHEN 'I'
                   PERFORM INQUIRY-CUSTOMER
               WHEN 'X'
                   CONTINUE
               WHEN OTHER
                   MOVE 'INVALID FUNCTION CODE ENTERED'
                       TO WS-MSG-FIELD
           END-EVALUATE.
      *
       ADD-CUSTOMER.
           PERFORM VALIDATE-CUSTOMER-INPUT
           IF WS-MSG-FIELD = SPACES
               MOVE SCR-CUSTOMER-ID TO CUST-ID
               MOVE SCR-CUSTOMER-NAME TO CUST-NAME
               MOVE SCR-CUSTOMER-ADDRESS TO CUST-ADDRESS
               MOVE SCR-CUSTOMER-PHONE TO CUST-PHONE
               MOVE SCR-CUSTOMER-EMAIL TO CUST-EMAIL
               MOVE SCR-CUSTOMER-STATUS TO CUST-STATUS
               MOVE ZEROES TO CUST-BALANCE
               MOVE SCR-CREDIT-LIMIT TO CUST-CREDIT-LIMIT
               WRITE CUSTOMER-RECORD
               IF WS-FILE-STATUS = '00'
                   MOVE 'CUSTOMER ADDED SUCCESSFULLY'
                       TO WS-MSG-FIELD
               ELSE IF WS-FILE-STATUS = '22'
                   MOVE 'CUSTOMER ID ALREADY EXISTS'
                       TO WS-MSG-FIELD
               ELSE
                   MOVE 'ERROR ADDING CUSTOMER RECORD'
                       TO WS-MSG-FIELD
               END-IF
           END-IF.
      *
       UPDATE-CUSTOMER.
           IF SCR-CUSTOMER-ID = SPACES
               MOVE 'CUSTOMER ID IS REQUIRED FOR UPDATE'
                   TO WS-MSG-FIELD
           ELSE
               MOVE SCR-CUSTOMER-ID TO CUST-ID
               READ CUSTOMER-FILE
               IF WS-FILE-STATUS = '00'
                   MOVE SCR-CUSTOMER-NAME TO CUST-NAME
                   MOVE SCR-CUSTOMER-ADDRESS TO CUST-ADDRESS
                   MOVE SCR-CUSTOMER-PHONE TO CUST-PHONE
                   MOVE SCR-CUSTOMER-EMAIL TO CUST-EMAIL
                   MOVE SCR-CUSTOMER-STATUS TO CUST-STATUS
                   REWRITE CUSTOMER-RECORD
                   IF WS-FILE-STATUS = '00'
                       MOVE 'CUSTOMER UPDATED SUCCESSFULLY'
                           TO WS-MSG-FIELD
                   ELSE
                       MOVE 'ERROR UPDATING CUSTOMER RECORD'
                           TO WS-MSG-FIELD
                   END-IF
               ELSE
                   MOVE 'CUSTOMER NOT FOUND'
                       TO WS-MSG-FIELD
               END-IF
           END-IF.
      *
       DELETE-CUSTOMER.
           IF SCR-CUSTOMER-ID = SPACES
               MOVE 'CUSTOMER ID IS REQUIRED FOR DELETE'
                   TO WS-MSG-FIELD
           ELSE
               MOVE SCR-CUSTOMER-ID TO CUST-ID
               READ CUSTOMER-FILE
               IF WS-FILE-STATUS = '00'
                   ACCEPT WS-CONFIRM
                   IF WS-CONFIRM = 'Y' OR WS-CONFIRM = 'y'
                       DELETE CUSTOMER-FILE RECORD
                       IF WS-FILE-STATUS = '00'
                           MOVE 'CUSTOMER DELETED SUCCESSFULLY'
                               TO WS-MSG-FIELD
                       ELSE
                           MOVE 'ERROR DELETING CUSTOMER RECORD'
                               TO WS-MSG-FIELD
                       END-IF
                   ELSE
                       MOVE 'DELETE OPERATION CANCELLED'
                           TO WS-MSG-FIELD
                   END-IF
               ELSE
                   MOVE 'CUSTOMER NOT FOUND'
                       TO WS-MSG-FIELD
               END-IF
           END-IF.
      *
       INQUIRY-CUSTOMER.
           IF SCR-CUSTOMER-ID = SPACES
               MOVE 'CUSTOMER ID IS REQUIRED FOR INQUIRY'
                   TO WS-MSG-FIELD
           ELSE
               MOVE SCR-CUSTOMER-ID TO CUST-ID
               READ CUSTOMER-FILE
               IF WS-FILE-STATUS = '00'
                   MOVE CUST-NAME TO SCR-CUSTOMER-NAME
                   MOVE CUST-ADDRESS TO SCR-CUSTOMER-ADDRESS
                   MOVE CUST-PHONE TO SCR-CUSTOMER-PHONE
                   MOVE CUST-EMAIL TO SCR-CUSTOMER-EMAIL
                   MOVE CUST-STATUS TO SCR-CUSTOMER-STATUS
                   MOVE CUST-BALANCE TO SCR-CUSTOMER-BALANCE
                   MOVE CUST-CREDIT-LIMIT TO SCR-CREDIT-LIMIT
                   MOVE 'CUSTOMER RECORD FOUND'
                       TO WS-MSG-FIELD
               ELSE
                   MOVE 'CUSTOMER NOT FOUND'
                       TO WS-MSG-FIELD
                   PERFORM INITIALIZE-SCREEN
               END-IF
           END-IF.
      *
       VALIDATE-CUSTOMER-INPUT.
           MOVE SPACES TO WS-MSG-FIELD
           IF SCR-CUSTOMER-ID = SPACES
               MOVE 'CUSTOMER ID IS REQUIRED'
                   TO WS-MSG-FIELD
           ELSE IF SCR-CUSTOMER-NAME = SPACES
               MOVE 'CUSTOMER NAME IS REQUIRED'
                   TO WS-MSG-FIELD
           ELSE IF SCR-CUSTOMER-PHONE NOT NUMERIC
               MOVE 'PHONE NUMBER MUST BE NUMERIC'
                   TO WS-MSG-FIELD
           ELSE IF SCR-CREDIT-LIMIT NOT NUMERIC
               MOVE 'CREDIT LIMIT MUST BE NUMERIC'
                   TO WS-MSG-FIELD
           ELSE IF SCR-CUSTOMER-STATUS NOT = 'A'
               AND SCR-CUSTOMER-STATUS NOT = 'I'
               MOVE 'STATUS MUST BE A (ACTIVE) OR I (INACTIVE)'
                   TO WS-MSG-FIELD
           END-IF.
      *
       CLEANUP-AND-EXIT.
           CLOSE CUSTOMER-FILE.
