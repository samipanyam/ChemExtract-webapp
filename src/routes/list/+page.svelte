<script>
  import { onMount} from 'svelte';
  import {getSmilesData, sendData} from '../../util'
  
  let names = [];

  let file_paths = [];

  onMount(async () => {
    // Fetch data on client side
    let data = await getSmilesData();
    names = data;
    console.log(data);
    console.log("hi");
    
  });

  console.log(names);

  // let names = ['test1', 'test2', 'test3', 'test4', 'test5', 'test6', 'test7', 'te
</script>

<body>
  <nav class="navbar">
    <!-- LOGO --> 
    <div class="logo"> 
      <!-- <img src="https://i.imgur.com/8Z5Zb5z.png" alt="logo" width="30px" height="30px"> -->
      <a href="/">ChemExtract </a>
    </div>
    <!-- NAVIGATION MENU -->
    <ul class="nav-links">
      <!-- NAVIGATION MENUS -->
      <div class="menu">
       <a href='about.svelte'> About</a>
       <a href='documentation.svelte'> Documentation</a>
       <a href='download.svelte'> Download</a>
              </div>
    </ul>
  </nav>
  </body>

<div class="list-wrapper">
  {#each names as name, i}
    <button class="list-item" on:click={sendData(name)}>
      <img class="list-item-image" src={'https://chemextract.s3.amazonaws.com/'+name.image } alt="{name.keyword}" onerror="this.style.display='none';">
      {#if name.keyword}
        <p class="list-item-text">{name.keyword}</p>
      {/if}
      <!-- <p class="list-item-text">{name['SMILES']}</p> -->
    </button>
  {/each}
</div>
  
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


    .menu > a{
        padding: 30px;
    }
   
    /* LOGO */    
    .logo {
    font-size: 32px;
    }

    .list-wrapper{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
      grid-auto-rows: minmax(4, 5);
      padding: .5%;

     
    }
    .list-item{
      text-align: center;
      width: 100%;
      outline:auto;
      outline-color: teal;
      background-color: #fff;
      color:teal;
    }
    
    .list-item:hover{

      background-color: white;
      opacity: .1;
      transition: all 250ms linear;
    }
    
    .list-item-image{
      width: 90%;
    

    }
    .list-item-image:hover{
      opacity:.1;
      transition: all 250ms linear;

    }
    .list-item-text{
      font-size: 1.5rem;
      font-weight: bold;
      color: teal;
      outline: none;
    
    }
    

</style>

