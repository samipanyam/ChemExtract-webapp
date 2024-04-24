<script>
  import { data, getPubchemData } from '../../util';
  import { onMount } from 'svelte';

  let names = [];
  let dataLoaded = false;
    let bob = "";
  onMount(async () => {
      // Fetch data on client side
      const responseData = await getPubchemData();
      
      names = responseData;
     
        console.log(names["origin"].split("/")[0]);
        console.log(names["origin"].split("/")[1]);
         bob  = "/src/" + names["origin"].split("/")[0]  +"/highlighted_" +names["origin"].split("/")[1] + ".pdf" 
        console.log(bob);
      // Set dataLoaded to true to indicate that data fetching is completed
      dataLoaded = true;
     

  });
  console.log(names);

  console.log(names["origin"]);
  
 
</script>


<main>
  <nav class="navbar">
    <!-- Your navigation menu -->
    <div class="logo"> 
        <a href="/">ChemExtract</a>
    </div>
    <ul class="nav-links">
        <div class="menu">
            <a href='/Download'>Download</a>
        </div>
    </ul>
  </nav>
  
  {#if dataLoaded}
      <div class="container1">
          <!-- Your main content -->
          <div class="wrapper1">
              <div class="chemical-image">
                  <img src="src/{names["Image"]}" alt="logo" class="img">
              </div>
          </div>
          <div class="wrapper2">
              <div class="chemical-stats">
                  {#each Object.entries(names) as [key, value]}
                      <div>{key}: {value}</div>
                      <br>
                  {/each}
              </div>
              
          </div>
      </div>
      <div class="container2">
        <!-- Your container2 content -->
        <div class="chemical-pdf">
          <iframe src={bob} title="PDF Viewer" width="100%" height="100%" frameborder="0"></iframe>
        </div>
        
      </div>
      
  {:else}
      <!-- Render a loading indicator or placeholder while data is loading -->
      <div>Loading...</div>
  {/if}
</main>





    
    
     
      
       
    
          
        <style>
            * {
              margin: 0;
              padding: 0;
              box-sizing: border-box;
            }
            
            body {
              font-family: cursive;
            }
            
            a {
              color: #fff;
              text-decoration: none;
            }
            
            .navbar {
              display: flex;
              align-items: center;
              justify-content: space-between;
              padding: 20px;
              background-color: teal;
              color: #fff;
            }
            
            .menu > a {
              padding: 30px;
            }
            
            .logo {
              font-size: 32px;
            }
          
              .container1 {
               float: left;
                width: 50%;
                padding: 10px;
                padding-right: 5px;
                justify-content: center;
                align-items: center;
                height: 100%;
              }
                .container2 {
                    float: left;
                    width: 50%;
                    padding: 10px;
                    padding-left: 5px;
                    height: 1000px;
                    justify-content: center;
                    align-items: center;
                }

                .wrapper1 {
                    padding-bottom: 5px;
                    justify-content: center;
                    height: 100%;
                }

                .wrapper2 {
                    padding-top: 5px;
                }
              

              
                
        
            .chemical-image {
                    
                    justify-content: center;
                    align-items: center;
                    outline: auto;
                    outline-color: teal;
                    padding: 10px;
                }
            .chemical-stats {
                    
                    outline: auto;
                    outline-color: teal;
                    padding: 10px;
                    justify-content: center;
                    align-items: center;
                   
            
                }

            .chemical-pdf{
                float:right;
                outline: auto;
                padding: 10px;
                outline-color: teal;
                width:100%;
                height:100%;
                justify-content: center;
                align-items: center;
               
            }
            
            .img {
                width: 100%;
                height: 30%;
            }
            .buttons {
                padding: 10px;
                justify-content: center;
                align-items: center;
                display: flex;
            
                
            }

            .navi-button {
                background-color: teal;
                color: #fff;
                border: none;
                padding: 10px 20px;
                border-radius: 5px;
                cursor: pointer;
                margin: 10px;
            }
            
            .page-selector {
               outline: auto;
                outline-color: teal;
            }
            .page-selector-unit {
                background-color: #fff;
                color: teal;
                border: none;
                padding: 10px 20px;
               
              
            }
            
            
    
    
            
            </style>
            