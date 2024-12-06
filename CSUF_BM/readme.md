
﻿
# Fullerton Black Market
The creation of a website that could help alleviate some of the potential economic burden amongst members of CSUF.
    
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/ktechhub/doctoc)*

<!---toc start-->

* [Fullerton Black Market](#fullerton-black-market)
  * [Description](#description)
  * [Installation](#installation)
  * [Diagram](#diagram)
  * [How to Run](#how-to-run)
  * [Known issues:](#known-issues)
  * [To-Do List:](#to-do-list)
      * [Credits](#credits)
        * [Donations](#donations)
          * [License](#license)

<!---toc end-->

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
  
## Description

CSUF Black Market is an e-commerce website that gives discounts for members of California State University of Fullerton (CSUF). Although, in order to get the discount, the **user must have a valid CSUF email.** Anyone without a CSUF email will still be able to sign-up and use the site like any other user (just without the discount).

  

## Installation
Clone from github
    

  

## Diagram

![](https://lh7-rt.googleusercontent.com/docsz/AD_4nXdp49gFGENESITgJghwPlbpvNw0p6qcFxwzestJdZs4zERBSU8hKTB8U86P-y1wmNpOPv0W3DO8_Nf4tT-DxIZxRELiTKUFAr7JZiktWM-Vl2HODrnuEP96K1TvD5FbWQZBIe9MtQauowAfGZR2ip4mf_IU?key=cBNfTfH-PDN5dLkNUc1p8g)

  

![](https://lh7-rt.googleusercontent.com/docsz/AD_4nXf7MAVzvQ1_cl9SuD6AGKyNdTasDBOW5CfnEDuuLMHaNtObeWjiAEpQrTLRv1Rc-0RGsyipZ9AM8Kuc6v2GfWimG5bj_HiprtNiG-_ahUUvH-YGI2Pl7WtRT4hQWst5a5XBxAz2jZp9a1hC2EFlHwxXNW4?key=cBNfTfH-PDN5dLkNUc1p8g)

## How to Run

- Editing settings.py
    

-   Please ensure you have a **SECRET_KEY** populated that is unique to your instance.  
    In order to generate a **SECRET KEY**, please use:
    ```bash 
    python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
    ```

-   Download dependencies
    

	```bash
		pip install Django mysqlclient Pillow python-decouple django-crispy-forms django-allauth django-countries django-phonenumber-field[phonenumberslite] django-storages  
	```
    
Here's a brief explanation of each dependency:
    
```
	Django: The web framework we're using.
    
	mysqlclient: Python interface to MySQL.
    
	Pillow: Python Imaging Library for image processing.
    
	python-decouple: Helps separate configuration from code.
    
	django-crispy-forms: Helps manage Django forms.
    
	django-allauth: Provides a set of Django applications addressing authentication, registration, account management.
    
	django-countries: Provides country choices for use with forms.
    
	django-phonenumber-field: A Django library which interfaces with python-phonenumbers to validate, pretty print and convert phone numbers.
    
	django-storages: A collection of custom storage backends for Django (optional, for cloud storage).
```

Run the following, once you're in the nested enterpriseApp folder that contains the manage.py: 
 ```bash
        Python manage.py makemigrations
  ```
 ```bash
        Python manage.py migrate
 ```
 ```bash
        Python manage.py runserver
 ```

  

## Known issues:

-   env file is not set for everyone. Users who clone/fork this will have to create a new env using command “python -m venv env”
    
-   Currently contains some codes that needs to be commented out in order to access the home page.
    
-   Must delete all migrations starting with “000” under the migrate folder and should use command “python manage.py makemigrations” then “python manage.py migrate” to have it up and running.
    

  

## To-Do List:

-   Redesigning/Reformatting of the front-end designs
    
-   Create an about-us page
    
-   Making a search bar
    
-   Include shipment/tracking info as well as design the page
    
-   Encryption of some of the user data
    

  

#### Credits
Tatiana, Andrew, Chris, Umar, Jesse, Nick, Troy

  

##### Donations

**Optional**. Any donations will be used to buy products to be able to sell at a more affordable price compared to stores.

  

###### License
[https://www.gnu.org/licenses/gpl-3.0.en.html](https://www.gnu.org/licenses/gpl-3.0.en.html)



